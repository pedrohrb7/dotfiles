-- Notification (naughty) configuration: borders, spacing and presets.
local naughty = require("naughty")
local beautiful = require("beautiful")
local dpi = require("beautiful.xresources").apply_dpi

naughty.config.defaults.border_width = dpi(3)
naughty.config.spacing = dpi(8)
naughty.config.padding = dpi(16)
naughty.config.defaults.margin = dpi(8)
naughty.config.defaults.timeout = 5

naughty.config.presets = {
	normal = {
		timeout = 4,
		fg = beautiful.color_red,
		bg = beautiful.border_normal,
		border_color = beautiful.color_green,
	},
	low = { timeout = 2, fg = beautiful.color_white, bg = beautiful.bg_focus, border_color = beautiful.color_green },
	critical = {
		border_width = 1,
		border_color = beautiful.color_red,
		fg = beautiful.border_normal,
		bg = beautiful.color_red,
		timeout = 0,
	},
}
