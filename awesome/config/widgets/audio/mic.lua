local awful = require("awful")
local wibox = require("wibox")

local volume_widget = wibox.widget({
	{
		id = "icon",
		widget = wibox.widget.imagebox,
		image = " ",
	},
	{
		id = "text",
		widget = wibox.widget.textbox,
		font = "FiraCode Nerd Font 9",
		align = "right",
	},
	layout = wibox.layout.fixed.horizontal,
})

local VOL_CMD = "pamixer --default-source --get-volume-human"

local update_volume_widget = function()
	awful.spawn.easy_async_with_shell(VOL_CMD, function(stdout)
		local volume_percentage = stdout
		if volume_percentage then
			volume_widget.text.text = " " .. volume_percentage
		end
	end)
end

update_volume_widget()
awful.widget.watch(VOL_CMD, 1, function()
	update_volume_widget()
end)

return wibox.container.margin(volume_widget, 10, 10)
