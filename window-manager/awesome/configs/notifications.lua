local awful = require("awful")
local wibox = require("wibox")
local gears = require("gears")
-- local ruled = require("ruled")
local naughty = require("naughty")
local beautiful = require("beautiful")
local dpi = beautiful.xresources.apply_dpi
-- local user = require("popups.user_profile")

--Color
local color = require("themes.color")

-- Config

naughty.config.defaults.ontop = true
naughty.config.defaults.screen = awful.screen.focused()
naughty.config.defaults.border_width = 0
naughty.config.defaults.position = "top_middle"
naughty.config.defaults.title = "Notification"
naughty.config.defaults.margin = dpi(16)
