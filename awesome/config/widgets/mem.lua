-- local awful = require("awful")
local beautiful = require("beautiful")
local watch = require("awful.widget.watch")
local wibox = require("wibox")

local ram_text_widget = {}

local function worker(user_args)
	local args = user_args or {}
	local timeout = args.timeout or 1
	local font = args.font or beautiful.font

	local ram_widget = wibox.widget({
		font = font,
		widget = wibox.widget.textbox,
	})

	watch('bash -c "LANGUAGE=en_US.UTF-8 free -h | grep Mem"', timeout, function(widget, stdout)
		local total, used = stdout:match("Mem:%s*(%S+)%s+(%S+)%s+(%S+)%s+(%S+)%s+(%S+)%s+(%S+)")
		widget:set_text("   " .. used)
	end, ram_widget)

	return ram_widget
end

return setmetatable(ram_text_widget, {
	__call = function(_, ...)
		return worker(...)
	end,
})
