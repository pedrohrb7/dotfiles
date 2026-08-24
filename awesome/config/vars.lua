-- Shared globals: modifier keys, default programs and layout order.
local awful = require("awful")

local M = {}

M.SUPER = "Mod4"
M.ALT = "Mod1"

M.terminal = "kitty"
M.fileManager = "kitty --hold sh -c 'yazi'"
M.browser = "vivaldi-stable"

-- Table of layouts to cover with awful.layout.inc, order matters.
M.layouts = {
	awful.layout.suit.tile,
	awful.layout.suit.floating,
	awful.layout.suit.tile.left,
	awful.layout.suit.tile.bottom,
	awful.layout.suit.tile.top,
	awful.layout.suit.spiral,
	awful.layout.suit.spiral.dwindle,
	awful.layout.suit.max,
	awful.layout.suit.max.fullscreen,
}

return M
