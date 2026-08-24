-- Brightness widget: plain text (via brightnessctl), same style as the
-- volume widget. Scroll up/down to increase/decrease brightness.
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

	local icon = "\u{f185}" -- sun-o

	local function update(_, stdout)
		local level = stdout:match("(%d+)%%") or "0"
		widget:set_text(icon .. " " .. level .. "%")
	end

	widget:buttons(awful.util.table.join(
		awful.button({}, 4, function()
			awful.spawn("brightnessctl set +" .. step .. "%", false)
		end),
		awful.button({}, 5, function()
			awful.spawn("brightnessctl set " .. step .. "%-", false)
		end)
	))

	watch("brightnessctl -m", timeout, update, widget)

	return widget
end

return setmetatable(M, {
	__call = function(_, ...)
		return worker(...)
	end,
})
