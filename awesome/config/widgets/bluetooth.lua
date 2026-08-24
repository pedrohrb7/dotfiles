-- Bluetooth widget: plain text (via bluetoothctl), same style as the volume
-- widget, instead of relying on blueman-applet's systray icon.
local awful = require("awful")
local wibox = require("wibox")
local watch = require("awful.widget.watch")
local gears = require("gears")

local M = {}

local function worker(args)
	args = args or {}
	local timeout = args.timeout or 5

	local widget = wibox.widget({
		id = "txt",
		widget = wibox.widget.textbox,
	})

	-- Material Design Icons glyphs render notably smaller than Font Awesome
	-- ones at the same point size in Nerd Fonts, so bump this one up.
	local icon = "<span size='150%'>󰂯</span>"

	local function update(_, stdout)
		local lines = {}
		for line in stdout:gmatch("[^\r\n]+") do
			table.insert(lines, line)
		end

		local powered = lines[1] == "on"

		local names = {}
		for i = 2, #lines do
			-- "Device XX:XX:XX:XX:XX:XX Some Name" -> "Some Name"
			local name = lines[i]:match("^Device %x%x:%x%x:%x%x:%x%x:%x%x:%x%x%s+(.+)$")
			if name then
				table.insert(names, name)
			end
		end

		if not powered then
			widget:set_markup(icon .. " off")
		elseif #names > 0 then
			local label = gears.string.xml_escape(table.concat(names, ", "))
			widget:set_markup(icon .. " " .. #names .. " (" .. label .. ")")
		else
			widget:set_markup(icon .. " not connected")
		end
	end

	widget:buttons(awful.util.table.join(awful.button({}, 1, function()
		awful.spawn("blueman-manager", false)
	end)))

	watch(
		"sh -c 'bluetoothctl show | grep -q \"Powered: yes\" && echo on || echo off; bluetoothctl devices Connected'",
		timeout,
		update,
		widget
	)

	return widget
end

return setmetatable(M, {
	__call = function(_, ...)
		return worker(...)
	end,
})
