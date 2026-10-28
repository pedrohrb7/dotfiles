-- Seção GPU do conky: ${lua gpu <campo>}, ${lua_graph gpu_util ...} e
-- ${lua_bar gpu_vram} em conky.text.
-- O conky do Void não é compilado com suporte a NVIDIA (sem ${nvidia}), então
-- os valores vêm do nvidia-smi. Uma chamada por atualização do conky serve
-- todos os campos: o resultado fica em cache até o contador ${updates} mudar.
-- O conky procura funções globais com prefixo conky_.
---@diagnostic disable: lowercase-global

local QUERY = "nvidia-smi --query-gpu=name,utilization.gpu,temperature.gpu,"
	.. "memory.used,memory.total,clocks.gr --format=csv,noheader,nounits 2>/dev/null"

local gpu = {}
local updated = nil

-- MiB -> texto no estilo de short_units do conky ("512M", "3.9G").
local function mib(value)
	if value < 1024 then
		return string.format("%dM", value)
	end
	return string.format("%.1fG", value / 1024)
end

local function refresh()
	local updates = conky_parse("${updates}")
	if updates == updated then
		return
	end
	updated = updates
	gpu = {}
	local f = io.popen(QUERY)
	if f == nil then
		return
	end
	local line = f:read("*l") or ""
	f:close()
	local name, util, temp, used, total, clock =
		line:match("^(.-), (%d+), (%d+), (%d+), (%d+), (%d+)$")
	if name == nil then
		return
	end
	used, total = tonumber(used), tonumber(total)
	gpu = {
		ok = "1",
		name = name:gsub("^NVIDIA ", ""):gsub("^GeForce ", ""),
		util = util,
		temp = temp,
		clock = clock,
		vram = mib(used) .. " / " .. mib(total),
		vram_perc = tostring(math.floor(used * 100 / total + 0.5)),
	}
end

-- ${lua gpu <campo>}: ok (1 se o nvidia-smi respondeu, senão 0), name, util,
-- temp, clock (MHz), vram ("usado / total"), vram_perc.
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
