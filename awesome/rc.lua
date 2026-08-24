-- If LuaRocks is installed, make sure that packages installed through it are
-- found (e.g. lgi). If LuaRocks is not installed, do nothing.
pcall(require, "luarocks.loader")

-- Error handling
require("config.handle-errors")

require("awful.hotkeys_popup.keys")
require("awful.autofocus")

local awful = require("awful")
local beautiful = require("beautiful")
local menubar = require("menubar")

local vars = require("config.vars")

beautiful.init(awful.util.get_configuration_dir() .. "config/theme.lua")

require("config.notifications")

beautiful.systray_icon_spacing = 8

awful.layout.layouts = vars.layouts

-- Menubar configuration
menubar.utils.terminal = vars.terminal

require("config.wibar").init()

-- Keys
local globalkeys = require("config.keys.global")
root.keys(globalkeys)

-- Rules
awful.rules.rules = require("config.rules")

-- Signals (client placement, titlebars, focus border)
require("config.signals")

-- Autostart applications
require("config.autostart").init()
