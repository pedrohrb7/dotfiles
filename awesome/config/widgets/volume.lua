-- Volume widget: plain text (via pamixer), colored by beautiful.fg_normal
-- instead of a systray icon, since GTK tray apps render their icons using
-- their own (often mismatched) color regardless of our theme.
local awful = require("awful")
local wibox = require("wibox")
local watch = require("awful.widget.watch")

local M = {}

local function worker(args)
	args = args or {}
	local step = args.step or 5
	local timeout = args.timeout or 2

	local widget = wibox.widget({
		id = "txt",
		widget = wibox.widget.textbox,
	})

	local function update(_, stdout)
		local lines = {}
		for line in stdout:gmatch("[^\r\n]+") do
			table.insert(lines, line)
		end

		local muted = lines[1] == "true"
		local level = tonumber(lines[2]) or 0

		local icon
		if muted or level == 0 then
			icon = "\u{f026}" -- volume-off
		elseif level < 50 then
			icon = "\u{f027}" -- volume-down
		else
			icon = "\u{f028}" -- volume-up
		end

		widget:set_text(muted and (icon .. " muted") or (icon .. " " .. level .. "%"))
	end

	widget:buttons(awful.util.table.join(
		awful.button({}, 1, function()
			awful.spawn("pamixer -t", false)
		end),
		awful.button({}, 2, function()
			awful.spawn("pavucontrol", false)
		end),
		awful.button({}, 4, function()
			awful.spawn("pamixer -i " .. step, false)
		end),
		awful.button({}, 5, function()
			awful.spawn("pamixer -d " .. step, false)
		end)
	))

	watch("sh -c 'pamixer --get-mute; pamixer --get-volume'", timeout, update, widget)

	return widget
end

return setmetatable(M, {
	__call = function(_, ...)
		return worker(...)
	end,
})
