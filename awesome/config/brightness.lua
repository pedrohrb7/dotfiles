-- Brightness control shared by the wibar widget and the brightness keys. The
-- backend is detected once at startup:
--   backlight: notebook panel (/sys/class/backlight), via brightnessctl.
--   ddc: external monitor over DDC/CI (VCP feature 0x10), via ddcutil. Needs
--     the i2c-dev module and access to /dev/i2c-*, see setup/README.md.
--   none: neither is available; the widget stays hidden and the keys do nothing.
-- Every new reading is broadcast as awesome.emit_signal("brightness::update", percent).
local awful = require("awful")
local gears = require("gears")

local M = {}

M.backend = nil -- "backlight", "ddc" or "none" once detected

local percent -- last known level
local listeners = {} -- callbacks waiting for detection

local function publish(value)
	value = tonumber(value)
	if value == nil then
		return
	end
	percent = math.max(0, math.min(100, math.floor(value + 0.5)))
	awesome.emit_signal("brightness::update", percent)
end

-- backlight -------------------------------------------------------------------

local backlight = {}

function backlight.read()
	awful.spawn.easy_async({ "brightnessctl", "-m" }, function(stdout)
		publish(stdout:match("(%d+)%%"))
	end)
end

function backlight.change(delta)
	local arg = delta >= 0 and ("+" .. delta .. "%") or (-delta .. "%-")
	awful.spawn.easy_async({ "brightnessctl", "set", arg }, backlight.read)
end

-- ddc -------------------------------------------------------------------------

-- ddcutil takes ~100-300 ms per call and the monitor rejects overlapping
-- requests, so calls run one at a time. Repeated key presses or scroll steps
-- while a call runs collapse into a single write of the latest target.
local ddc = { bus = nil, max = 100, busy = false, target = nil }

local function ddcutil(args, callback)
	local cmd = { "ddcutil", "--bus", ddc.bus }
	for _, arg in ipairs(args) do
		table.insert(cmd, arg)
	end
	awful.spawn.easy_async(cmd, callback)
end

-- "VCP 10 C 50 100" -> current 50, max 100
function ddc.read()
	if ddc.busy then
		return
	end
	ddc.busy = true
	ddcutil({ "getvcp", "10", "--brief" }, function(stdout)
		ddc.busy = false
		local current, max = stdout:match("VCP 10 C (%d+) (%d+)")
		if current then
			ddc.max = tonumber(max) > 0 and tonumber(max) or 100
			publish(tonumber(current) * 100 / ddc.max)
		end
		ddc.flush()
	end)
end

function ddc.flush()
	if ddc.busy or ddc.target == nil then
		return
	end
	local target = ddc.target
	ddc.target = nil
	ddc.busy = true
	publish(target)
	local raw = math.floor(target * ddc.max / 100 + 0.5)
	ddcutil({ "--noverify", "setvcp", "10", tostring(raw) }, function()
		ddc.busy = false
		ddc.flush()
	end)
end

function ddc.change(delta)
	if percent == nil then
		return
	end
	local base = ddc.target or percent
	ddc.target = math.max(0, math.min(100, base + delta))
	ddc.flush()
end

-- detection -------------------------------------------------------------------

local BACKENDS = { backlight = backlight, ddc = ddc }

-- First /dev/i2c-N of `ddcutil detect --terse` is the first DDC/CI monitor.
local DETECT = [[
if [ -n "$(ls -A /sys/class/backlight 2>/dev/null)" ] && command -v brightnessctl >/dev/null; then
	echo backlight
elif command -v ddcutil >/dev/null; then
	bus=$(ddcutil detect --terse 2>/dev/null | sed -n 's|.*/dev/i2c-\([0-9]*\).*|\1|p' | head -n 1)
	[ -n "$bus" ] && echo "ddc $bus" || echo none
else
	echo none
fi]]

local function detected(backend, bus)
	M.backend = backend
	ddc.bus = bus
	local impl = BACKENDS[backend]
	if impl then
		impl.read()
	end
	for _, callback in ipairs(listeners) do
		callback(backend)
	end
	listeners = {}
end

-- Detects the backend and polls the level every `timeout` seconds so changes
-- made elsewhere (monitor buttons, another tool) show up. DDC polls slower:
-- each read goes through the monitor's I2C bus.
function M.init(args)
	args = args or {}
	awful.spawn.easy_async_with_shell(DETECT, function(stdout)
		local backend, bus = stdout:match("^(%a+)%s*(%d*)")
		detected(backend or "none", bus ~= "" and bus or nil)
		local impl = BACKENDS[M.backend]
		if impl then
			gears.timer({
				timeout = M.backend == "ddc" and (args.ddc_timeout or 30) or (args.timeout or 2),
				autostart = true,
				callback = impl.read,
			})
		end
	end)
end

-- Calls callback(backend) once the backend is known (right away if it is).
function M.on_detect(callback)
	if M.backend then
		callback(M.backend)
	else
		table.insert(listeners, callback)
	end
end

-- Changes the brightness by delta percent (negative to decrease).
function M.change(delta)
	local impl = BACKENDS[M.backend]
	if impl then
		impl.change(delta)
	end
end

function M.get()
	return percent
end

return M
