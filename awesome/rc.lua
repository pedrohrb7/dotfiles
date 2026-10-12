-- If LuaRocks is installed, make sure that packages installed through it are
-- found (e.g. lgi). If LuaRocks is not installed, do nothing.
pcall(require, "luarocks.loader")

-- Error handling
require("config.handle-errors")

-- Standard awesome library
local awful = require("awful")

require("awful.autofocus")

-- Enable hotkeys help widget for VIM and other apps
-- when client with a matching name is opened:
require("awful.hotkeys_popup.keys")

-- {{{ Theme
local beautiful = require("beautiful")
beautiful.init(require("config.theme"))
-- }}}

-- {{{ Root window cursor (theme comes from Xcursor.theme in ~/.Xresources)
root.cursor("left_ptr")
-- }}}

require("config.notifications")

-- {{{ Low battery notifications
require("config.battery").init()
-- }}}

-- {{{ Wibar
require("config.wibar").init()
-- }}}

-- {{{ Keyboard layouts
require("config.keyboard").init()
-- }}}

-- {{{ Key bindings
root.keys(require("config.keys.global"))
-- Client keys/buttons are applied through the default rule in config/rules.lua
-- }}}

-- {{{ Rules
awful.rules.rules = require("config.rules")
-- }}}

-- {{{ Signals
require("config.signals")
-- }}}

-- {{{ Autostart
require("config.autostart").init()
-- }}}
