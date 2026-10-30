-- Seções do conky que dependem do hardware: ${lua_parse disks},
-- ${lua_parse network} e ${lua_parse battery} em conky.text.
-- Cada função detecta o que existe na máquina (pontos de montagem, discos,
-- interfaces de rede, bateria) e devolve o texto da seção com as variáveis do
-- conky já apontando para os nomes certos, então o mesmo conky.conf serve em
-- qualquer máquina. A detecção roda a cada INTERVAL segundos; os valores em si
-- (uso, velocidade, carga) são atualizados pelo conky a cada update_interval.
-- O conky procura funções globais com prefixo conky_.
---@diagnostic disable: lowercase-global

local INTERVAL = 10 -- segundos entre detecções

local function read_file(path)
	local f = io.open(path, "r")
	if f == nil then
		return nil
	end
	local value = f:read("*l")
	f:close()
	return value
end

local function lines(cmd)
	local result = {}
	local f = io.popen(cmd)
	if f == nil then
		return result
	end
	for line in f:lines() do
		table.insert(result, line)
	end
	f:close()
	return result
end

-- Guarda o texto gerado por build por INTERVAL segundos.
local function cached(build)
	local text, updated = "", -INTERVAL
	return function()
		if os.time() - updated >= INTERVAL then
			text = build()
			updated = os.time()
		end
		return text
	end
end

-- Disco -----------------------------------------------------------------------

-- Pontos de montagem que não interessam no painel.
local IGNORED_MOUNTS = { "^/boot", "^/efi", "^/var/lib/docker", "^/snap" }

local function ignored(mountpoint)
	for _, pattern in ipairs(IGNORED_MOUNTS) do
		if mountpoint:find(pattern) then
			return true
		end
	end
	return false
end

-- Um ponto de montagem por partição, na ordem de /proc/mounts ("/" primeiro):
-- binds da mesma partição (ex.: /var/lib/docker) ficam de fora.
local function mounts()
	local result, seen = {}, {}
	for _, line in ipairs(lines("cat /proc/mounts")) do
		local source, mountpoint = line:match("^/dev/(%S+) (%S+)")
		if source and not source:find("^loop") and not seen[source] and not ignored(mountpoint) then
			seen[source] = true
			-- /proc/mounts escapa espaço como \040
			table.insert(result, { source = source, mountpoint = mountpoint:gsub("\\040", " ") })
		end
	end
	return result
end

-- Disco que contém a partição: nvme0n1p1 -> nvme0n1, sda2 -> sda.
local function parent_disk(partition)
	if read_file("/sys/class/block/" .. partition .. "/partition") == nil then
		return partition
	end
	local path = lines("readlink -f /sys/class/block/" .. partition)[1] or ""
	return path:match("([^/]+)/[^/]+$") or partition
end

-- Índice do hwmon de cada disco (nvme e drivetemp), para ${hwmon N temp 1}.
local function disk_hwmons()
	local result = {}
	for _, line in ipairs(lines('for h in /sys/class/hwmon/hwmon*; do echo "${h##*hwmon} $(readlink -f "$h")"; done')) do
		local index, path = line:match("^(%d+) (.+)$")
		if index then
			result[path] = index
		end
	end
	return result
end

local function disk_hwmon(disk, hwmons)
	local device = lines("readlink -f /sys/block/" .. disk .. "/device")[1]
	if device == nil or device == "" then
		return nil
	end
	for path, index in pairs(hwmons) do
		if path:sub(1, #device + 1) == device .. "/" then
			return index
		end
	end
	return nil
end

local function disk_kind(disk)
	if disk:find("^nvme") then
		return "NVMe"
	elseif read_file("/sys/block/" .. disk .. "/removable") == "1" then
		return "USB"
	elseif read_file("/sys/block/" .. disk .. "/queue/rotational") == "1" then
		return "HDD"
	end
	return "SSD"
end

local function build_disks()
	local out, disks, seen = {}, {}, {}
	for _, m in ipairs(mounts()) do
		local p = m.mountpoint
		table.insert(out, string.format(
			"${color2}%s${alignr}${color0}${fs_used %s} / ${fs_size %s}${color2}  ${if_match ${fs_used_perc %s} >= 90}${color7}${else}${color}${endif}${fs_used_perc %s}%%",
			p, p, p, p, p
		))
		table.insert(out, string.format("${if_match ${fs_used_perc %s} >= 90}${color7}${else}${color4}${endif}${fs_bar %s}", p, p))
		local disk = parent_disk(m.source)
		if not seen[disk] then
			seen[disk] = true
			table.insert(disks, disk)
		end
	end

	-- Rótulo pelo tipo; com dois discos do mesmo tipo, pelo nome.
	local kinds, count = {}, {}
	for _, disk in ipairs(disks) do
		kinds[disk] = disk_kind(disk)
		count[kinds[disk]] = (count[kinds[disk]] or 0) + 1
	end

	local hwmons = disk_hwmons()
	for _, disk in ipairs(disks) do
		local label = count[kinds[disk]] > 1 and disk or kinds[disk]
		local hwmon = disk_hwmon(disk, hwmons)
		local temp = hwmon and string.format("${color2}  ·  ${color0}${hwmon %s temp 1}°C", hwmon) or ""
		table.insert(out, string.format(
			"${color2}%s I/O${alignr}${color5}󰁅 ${color0}${diskio_read %s}  ${color6}󰁝 ${color0}${diskio_write %s}%s",
			label, disk, disk, temp
		))
	end
	return table.concat(out, "\n")
end

-- ${lua_parse disks}: uso de cada ponto de montagem (vermelho a partir de 90%)
-- e I/O + temperatura de cada disco.
conky_disks = cached(build_disks)

-- Rede ------------------------------------------------------------------------

local function interfaces()
	return lines("ls /sys/class/net")
end

local function build_network()
	local wifi, ethernet, vpn = {}, {}, {}
	for _, iface in ipairs(interfaces()) do
		local base = "/sys/class/net/" .. iface
		if read_file(base .. "/phy80211/name") then
			table.insert(wifi, iface)
		elseif read_file(base .. "/tun_flags") or iface:find("^wg") then
			table.insert(vpn, iface)
		elseif read_file(base .. "/device/uevent") then
			-- Só placas físicas: docker0, veth*, br-* não têm device
			table.insert(ethernet, iface)
		end
	end

	local out = {}
	for _, i in ipairs(wifi) do
		table.insert(out, string.format(
			"${if_up %s}${color2}Wi-Fi${alignr}${color0}${wireless_essid %s}${color2}  ${color}${wireless_link_qual_perc %s}%%\n${template4 %s}\n${endif}",
			i, i, i, i
		))
	end
	for _, i in ipairs(ethernet) do
		table.insert(out, string.format("${if_up %s}${template1 Ethernet %s}\n${template4 %s}\n${endif}", i, i, i))
	end
	for _, i in ipairs(vpn) do
		table.insert(out, string.format("${if_up %s}${color2}VPN${alignr}${color0}${addr %s}\n${endif}", i, i))
	end
	return table.concat(out)
end

-- ${lua_parse network}: um bloco por interface com IP: Wi-Fi (rede e sinal),
-- Ethernet e VPN (tun/tap/WireGuard).
conky_network = cached(build_network)

-- Bateria ---------------------------------------------------------------------

-- Bateria do próprio notebook: scope "Device" é bateria de periférico
-- (mouse, controle), que aparece na seção Bluetooth.
local function battery_name()
	for _, name in ipairs(lines("ls /sys/class/power_supply")) do
		local base = "/sys/class/power_supply/" .. name
		if read_file(base .. "/type") == "Battery" and read_file(base .. "/scope") ~= "Device" then
			return name
		end
	end
	return nil
end

local function build_battery()
	local b = battery_name()
	if b == nil then
		return ""
	end
	return (string.gsub([[


${template0 󰁹 BATERIA}
${color2}${battery_status {bat}}${alignr}${if_match ${battery_percent {bat}} <= 20}${color7}${else}${color0}${endif}${battery_percent {bat}}%
${if_match ${battery_percent {bat}} <= 20}${color7}${else}${color5}${endif}${battery_bar {bat}}
${if_match "${battery_status {bat}}" == "discharging"}${color2}Restante${alignr}${color0}${battery_time {bat}}
${endif}${if_match "${battery_status {bat}}" == "charging"}${color2}Até carregar${alignr}${color0}${battery_time {bat}}
${endif}]], "{bat}", b))
end

-- ${lua_parse battery}: seção inteira (com cabeçalho) só quando há bateria.
conky_battery = cached(build_battery)
