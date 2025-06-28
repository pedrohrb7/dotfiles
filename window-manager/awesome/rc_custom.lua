-- If LuaRocks is installed, make sure that packages installed through it are
-- found (e.g. lgi). If LuaRocks is not installed, do nothing.
pcall(require, "luarocks.loader")

-- Import Section - Import all libs here
-- Enable hotkeys help widget for VIM and other apps
-- when client with a matching name is opened:
require("awful.hotkeys_popup.keys")
require("awful.autofocus")

-- Import status bar
require("configs.statusbar")

--Notifications
require("configs.notifications")

-- Error handling
require("configs.handle-errors")

-- Standard awesome library
local gears = require("gears")
local awful = require("awful")

-- Theme handling library
local beautiful = require("beautiful")

local menubar = require("menubar")
-- End Import section

RC = {} -- global namespace, on top before require any modules
RC.vars = require("configs.variables")

-- Themes define colours, icons, font and wallpapers.
beautiful.init(gears.filesystem.get_themes_dir() .. "default/theme.lua")
beautiful.wallpaper = RC.vars.wallpaper

-- Default
local modkey = RC.vars.modkey

local main = {
	layouts = require("configs.layouts"),
	tags = require("configs.tags"),
	menu = require("configs.menu"),
	-- rules = require("main.rules"),
}

-- Layouts
RC.layouts = main.layouts()

-- Tags
RC.tags = main.tags()

--  Menu
RC.mainmenu = awful.menu({
	items = main.menu(),
	theme = {
		width = 250,
		height = 30,
		font = "FiraCode Nerd Font 10",
		bg_normal = "#00000080",
		bg_focus = "#729fcf",
		border_width = 3,
		border_color = "#000000",
	},
})

RC.launcher = awful.widget.launcher({ image = beautiful.awesome_icon })

-- Menubar configuration
menubar.utils.terminal = RC.vars.terminal

-- Keyboard map indicator and switcher
-- mykeyboardlayout = awful.widget.keyboardlayout()

--Gaps
beautiful.useless_gap = 4

awful.util.spawn("nm-applet")
