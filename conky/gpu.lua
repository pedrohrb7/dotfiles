-- Seção GPU do conky: ${lua gpu <campo>}, ${lua_graph gpu_util ...} e
-- ${lua_bar gpu_vram} em conky.text.
-- A placa é detectada uma vez, ao carregar o Lua:
--   nvidia: o conky do Void não é compilado com suporte a NVIDIA (sem
--     ${nvidia}), então os valores vêm do nvidia-smi. Só é usado se ele
--     responder (driver carregado).
--   intel: iGPU com driver i915 ou xe, lida direto do sysfs, sem root. O uso
--     vem da residência RC6 (tempo que a GPU passou dormindo), a temperatura é
--     a do pacote da CPU (a iGPU não tem sensor próprio) e não há VRAM (a
--     memória é a RAM).
-- Uma leitura por atualização do conky serve todos os campos: o resultado
-- fica em cache até o contador ${updates} mudar.
-- O conky procura funções globais com prefixo conky_.
---@diagnostic disable: lowercase-global

local NVIDIA_QUERY = "nvidia-smi --query-gpu=name,utilization.gpu,temperature.gpu,"
	.. "memory.used,memory.total,clocks.gr --format=csv,noheader,nounits 2>/dev/null"

local function read_file(path)
	local f = io.open(path, "r")
	if f == nil then
		return nil
	end
	local value = f:read("*l")
	f:close()
	return value
end

local function read_number(path)
	return tonumber(read_file(path) or "")
end

local function first_line(cmd)
	local f = io.popen(cmd)
	if f == nil then
		return nil
	end
	local line = f:read("*l")
	f:close()
	return line
end

local function first_existing(paths)
	for _, path in ipairs(paths) do
		if read_file(path) ~= nil then
			return path
		end
	end
	return nil
end

-- MiB -> texto no estilo de short_units do conky ("512M", "3.9G").
local function mib(value)
	if value < 1024 then
		return string.format("%dM", value)
	end
	return string.format("%.1fG", value / 1024)
end

local function parse_nvidia(line)
	local name, util, temp, used, total, clock =
		(line or ""):match("^(.-), (%d+), (%d+), (%d+), (%d+), (%d+)$")
	if name == nil then
		return nil
	end
	used, total = tonumber(used), tonumber(total)
	return {
		ok = "1",
		name = name:gsub("^NVIDIA ", ""):gsub("^GeForce ", ""),
		util = util,
		temp = temp,
		clock = clock,
		has_vram = "1",
		vram = mib(used) .. " / " .. mib(total),
		vram_perc = tostring(math.floor(used * 100 / total + 0.5)),
	}
end

local function nvidia_backend()
	if parse_nvidia(first_line(NVIDIA_QUERY)) == nil then
		return nil
	end
	return {
		read = function()
			return parse_nvidia(first_line(NVIDIA_QUERY))
		end,
	}
end

-- Pasta do hwmon com o nome dado ("coretemp" para Intel, "k10temp" para AMD).
local function hwmon_dir(names)
	for i = 0, 31 do
		local dir = "/sys/class/hwmon/hwmon" .. i
		local name = read_file(dir .. "/name")
		for _, wanted in ipairs(names) do
			if name == wanted then
				return dir
			end
		end
	end
	return nil
end

-- "CoffeeLake-S GT2 [UHD Graphics 630]" (lspci -mm) -> "UHD Graphics 630".
local function intel_name(slot)
	local line = first_line("lspci -mm -s " .. slot .. " 2>/dev/null") or ""
	local device = line:match('^%S+ "[^"]*" "[^"]*" "([^"]*)"') or ""
	return device:match("%[(.-)%]") or (device ~= "" and device) or "Intel iGPU"
end

-- Placa DRM da iGPU Intel: o caminho de cada contador muda entre i915 (antigo
-- e novo, com gt/gt0) e xe.
local function intel_card()
	for i = 0, 7 do
		local card = "/sys/class/drm/card" .. i
		if read_file(card .. "/device/vendor") == "0x8086" then
			local idle = first_existing({
				card .. "/gt/gt0/rc6_residency_ms",
				card .. "/power/rc6_residency_ms",
				card .. "/device/tile0/gt0/gtidle/idle_residency_ms",
			})
			local freq = first_existing({
				card .. "/gt/gt0/rps_act_freq_mhz",
				card .. "/gt_act_freq_mhz",
				card .. "/device/tile0/gt0/freq0/act_freq",
			})
			if idle and freq then
				local slot = (first_line("readlink -f " .. card .. "/device") or ""):match("[^/]+$") or ""
				return { idle = idle, freq = freq, slot = slot }
			end
		end
	end
	return nil
end

-- Segundos desde o boot com resolução de 10 ms (os.time só tem segundos).
local function uptime_ms()
	local line = read_file("/proc/uptime") or ""
	return (tonumber(line:match("^(%S+)")) or 0) * 1000
end

local function intel_backend()
	local card = intel_card()
	if card == nil then
		return nil
	end
	local name = intel_name(card.slot)
	local temp_input = (hwmon_dir({ "coretemp", "k10temp" }) or "") .. "/temp1_input"
	local last_idle, last_time = read_number(card.idle), uptime_ms()
	local util = 0

	return {
		read = function()
			local idle, now = read_number(card.idle), uptime_ms()
			if idle and last_idle and now > last_time then
				local busy = 100 - (idle - last_idle) * 100 / (now - last_time)
				util = math.floor(math.max(0, math.min(100, busy)) + 0.5)
			end
			last_idle, last_time = idle, now
			local temp = read_number(temp_input)
			return {
				ok = "1",
				name = name,
				util = tostring(util),
				temp = temp and tostring(math.floor(temp / 1000 + 0.5)) or "?",
				clock = tostring(read_number(card.freq) or 0),
				has_vram = "0",
			}
		end,
	}
end

local backend = nvidia_backend() or intel_backend()
local gpu = {}
local updated = nil

local function refresh()
	local updates = conky_parse("${updates}")
	if updates == updated then
		return
	end
	updated = updates
	gpu = backend and backend.read() or {}
end

-- ${lua gpu <campo>}: ok (1 se a placa foi lida, senão 0), name, util, temp,
-- clock (MHz), has_vram (1 se tem VRAM dedicada), vram ("usado / total"),
-- vram_perc.
function conky_gpu(field)
	refresh()
	return gpu[field] or (field == "ok" and "0" or "")
end

-- ${lua_graph gpu_util ...}: uso da GPU em %.
function conky_gpu_util()
	refresh()
	return tonumber(gpu.util) or 0
end

-- ${lua_bar gpu_vram}: VRAM usada em %.
function conky_gpu_vram()
	refresh()
	return tonumber(gpu.vram_perc) or 0
end
