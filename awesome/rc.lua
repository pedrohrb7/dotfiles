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

require("config.notifications")

-- {{{ Wibar
require("config.wibar").init()
-- }}}

-- {{{ Key bindings
globalkeys = require("config.keys.global")
root.keys(globalkeys)

local clientkeymaps = require("config.keys.client")
clientkeys = clientkeymaps.clientkeys
clientbuttons = clientkeymaps.clientbuttons
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
