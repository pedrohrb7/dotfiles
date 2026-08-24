-- Mic widget: plain text (via pamixer --default-source), same style as the
-- volume widget. Left click mutes/unmutes, middle click opens pavucontrol.
local awful = require("awful")
local wibox = require("wibox")
local watch = require("awful.widget.watch")

local M = {}

local function worker(args)
	args = args or {}
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
		local level = lines[2] or "0"

		local icon = muted and "\u{f131}" or "\u{f130}" -- microphone-slash / microphone

		widget:set_text(muted and (icon .. " muted") or (icon .. " " .. level .. "%"))
	end

	widget:buttons(awful.util.table.join(
		awful.button({}, 1, function()
			awful.spawn("pamixer --default-source -t", false)
		end),
		awful.button({}, 2, function()
			awful.spawn("pavucontrol", false)
		end)
	))

	watch("sh -c 'pamixer --default-source --get-mute; pamixer --default-source --get-volume'", timeout, update, widget)

	return widget
end

return setmetatable(M, {
	__call = function(_, ...)
		return worker(...)
	end,
})
