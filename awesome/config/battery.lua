-- Low battery notifications (no wibar widget). Polls the kernel power_supply
-- uevents and notifies once per threshold crossed while discharging: a normal
-- notification at LOW percent, a sticky critical one at CRITICAL percent. Plugging
-- the charger dismisses the warning and re-arms both thresholds. Reaching 100% on
-- the charger shows a low priority "charged" notification, once per unplug.
local awful = require("awful")
local gears = require("gears")
local naughty = require("naughty")

local M = {}

M.LOW = 20
M.CRITICAL = 10

local ICON = "\u{f244}" -- battery-empty

-- Each uevent file is a block of POWER_SUPPLY_KEY=value lines starting with NAME
local function parse_supplies(stdout)
	local supplies = {}
	local current
	for key, value in stdout:gmatch("POWER_SUPPLY_([%w_]+)=([^\n]*)") do
		if key == "NAME" then
			current = {}
			table.insert(supplies, current)
		elseif current then
			current[key:lower()] = tonumber(value) or value
		end
	end
	return supplies
end

-- Combines every present battery into a single reading. Returns nil when there is
-- no battery or the reading is impossible: some fuel gauges get stuck reporting
-- 0% while the machine runs on battery, which would raise a false alarm forever.
local function read_state(supplies)
	local on_ac, charging, full_count = false, false, 0
	local now, full, capacity_sum, batteries = 0, 0, 0, 0

	for _, supply in ipairs(supplies) do
		if supply.type == "Mains" and supply.online == 1 then
			on_ac = true
		elseif supply.type == "Battery" and supply.present == 1 then
			batteries = batteries + 1
			if supply.status == "Charging" then
				on_ac, charging = true, true
			elseif supply.status == "Full" then
				on_ac, full_count = true, full_count + 1
			end
			now = now + (supply.energy_now or supply.charge_now or 0)
			full = full + (supply.energy_full or supply.charge_full or 0)
			capacity_sum = capacity_sum + (supply.capacity or 0)
		end
	end

	if batteries == 0 then
		return nil
	end

	local percent = full > 0 and math.floor(now / full * 100 + 0.5) or math.floor(capacity_sum / batteries)
	if percent <= 0 and not on_ac then
		return nil
	end

	-- On AC but neither charging nor full means a charge threshold or a hold
	local status = (not on_ac and "discharging")
		or (charging and "charging")
		or (full_count == batteries and "full")
		or "plugged"

	return { percent = percent, on_ac = on_ac, status = status }
end

local DEFAULT_PATH = "/sys/class/power_supply"

-- Reads every uevent under path and calls callback with read_state's result
local function read(path, callback)
	awful.spawn.easy_async({ "sh", "-c", 'cat "$1"/*/uevent', "sh", path }, function(stdout)
		callback(read_state(parse_supplies(stdout)))
	end)
end

-- Font Awesome battery glyph matching the charge, from empty to full
local function level_icon(percent)
	local icons = { "\u{f244}", "\u{f243}", "\u{f242}", "\u{f241}", "\u{f240}" }
	return icons[math.min(5, math.floor(percent / 20) + 1)]
end

local STATUS_TEXT = {
	charging = "Charging",
	full = "Fully charged",
	plugged = "Plugged in, not charging",
	discharging = "On battery",
}

local status_notification

-- On-demand battery status (bound to a key). Replaces its own previous popup.
function M.show(args)
	args = args or {}
	read(args.path or DEFAULT_PATH, function(state)
		local title, text
		if state then
			title = level_icon(state.percent) .. "  Battery " .. state.percent .. "%"
			text = STATUS_TEXT[state.status]
		else
			title = ICON .. "  Battery"
			text = "No battery reading available"
		end
		status_notification = naughty.notify({
			title = title,
			text = text,
			timeout = 5,
			replaces_id = status_notification and status_notification.id or nil,
			destroy = function()
				status_notification = nil
			end,
		})
	end)
end

local function create(args)
	args = args or {}
	local path = args.path or DEFAULT_PATH
	local level -- nil, "low" or "critical": the last warning shown since unplugging
	local notification
	-- nil until the first reading, then whether "charged" was shown since unplugging
	local full_notified

	local function dismiss()
		if notification then
			naughty.destroy(notification, naughty.notificationClosedReason.dismissedByCommand)
			notification = nil
		end
	end

	local function warn(new_level, state)
		level = new_level
		local critical = new_level == "critical"
		notification = naughty.notify({
			preset = critical and naughty.config.presets.critical or naughty.config.presets.normal,
			title = ICON .. "  " .. (critical and "Battery critical" or "Battery low"),
			text = string.format("%d%% remaining%s", state.percent, critical and " - plug in the charger now" or ""),
			timeout = not critical and 10 or nil,
			replaces_id = notification and notification.id or nil,
			destroy = function()
				notification = nil
			end,
		})
	end

	-- Some gauges never report "Full" and just sit at 100% while not charging
	local function update_full(state)
		local full = state.on_ac and (state.status == "full" or state.percent >= 100)
		if not state.on_ac then
			full_notified = false
		elseif full and full_notified == false then
			full_notified = true
			naughty.notify({
				preset = naughty.config.presets.low,
				title = level_icon(100) .. "  Battery charged",
				text = "100% - you can unplug the charger",
				timeout = 5,
			})
		elseif full_notified == nil then
			-- First reading: stay quiet if it was already full when awesome started
			full_notified = full
		end
	end

	local function update(state)
		if not state then
			return
		end
		update_full(state)
		if state.on_ac then
			level = nil
			dismiss()
		elseif state.percent <= M.CRITICAL and level ~= "critical" then
			warn("critical", state)
		elseif state.percent <= M.LOW and level == nil then
			warn("low", state)
		end
	end

	local function check()
		read(path, update)
	end

	return gears.timer({
		timeout = args.timeout or 60,
		autostart = true,
		call_now = true,
		callback = check,
	})
end

function M.init(args)
	return create(args)
end

return M
