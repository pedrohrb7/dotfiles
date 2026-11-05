-- Brightness widget: plain text, same style as the volume widget. Scroll
-- up/down to increase/decrease brightness. The level comes from
-- config/brightness.lua (notebook backlight or external monitor over DDC/CI);
-- the widget stays hidden on machines with neither.
local awful = require("awful")
local wibox = require("wibox")

local brightness = require("config.brightness")

local M = {}

local function worker(args)
	args = args or {}
	local step = args.step or 5

	local widget = wibox.widget({
		id = "txt",
		widget = wibox.widget.textbox,
		visible = false,
	})

	local icon = "\u{f185}" -- sun-o

	local function update(level)
		widget:set_text(icon .. " " .. level .. "%")
	end

	awesome.connect_signal("brightness::update", update)
	if brightness.get() then
		update(brightness.get())
	end
	brightness.on_detect(function(backend)
		widget.visible = backend ~= "none"
	end)

	widget:buttons(awful.util.table.join(
		awful.button({}, 4, function()
			brightness.change(step)
		end),
		awful.button({}, 5, function()
			brightness.change(-step)
		end)
	))

	return widget
end

return setmetatable(M, {
	__call = function(_, ...)
		return worker(...)
	end,
})
