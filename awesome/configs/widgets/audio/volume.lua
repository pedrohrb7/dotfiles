-- --------------------------------------------
-- Volume widget for Awesome WM
-- Shows volume level
--
-- @author Pedro Borges
--
-- Highly inspired by this widget code
-- https://github.com/streetturtle/awesome-wm-widgets/tree/master/brightness-widget
-- @author Pavel Makhov
-- @copyright 2021 Pavel Makhov
-- --------------------------------------------

local awful = require("awful")
local wibox = require("wibox")

local volume_widget = wibox.widget({
	{
		id = "icon",
		widget = wibox.widget.imagebox,
		image = " ", -- Replace with an actual path to an icon
	},
	{
		id = "text",
		widget = wibox.widget.textbox,
		font = "FiraCode Nerd Font 8",
		align = "right",
	},
	layout = wibox.layout.fixed.horizontal,
})

-- Update the volume widget
local update_volume_widget = function()
	awful.spawn.easy_async_with_shell("pamixer --get-volume-human", function(stdout)
		local volume_percentage = stdout
		if volume_percentage then
			volume_widget.text.text = " " .. volume_percentage
			-- Optional: Change icon based on mute status or volume level
			-- For example, check mute status using `amixer get Master | grep -oP '\\[(on|off)\\]'`
		end
	end)
end

-- Initial update and periodic updates
update_volume_widget()
awful.widget.watch(
	"pamixer --get-volume-human",
	1, -- Update every 1 second
	function()
		update_volume_widget()
	end
)

return wibox.container.margin(volume_widget, 10, 10)
