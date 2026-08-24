-- Autostart: launches tray/compositor helpers, guarding each against
-- duplicate instances across awesome restarts (theme switch, etc).
local awful = require("awful")

local M = {}

local function run_once(prog, cmd)
	cmd = cmd or prog
	awful.spawn.with_shell(string.format("pgrep -u $USER -x %s > /dev/null || (%s)", prog, cmd))
end

function M.init()
	run_once("nm-applet")
	run_once("blueman-applet")
	run_once("artix-pipewire-launcher")
	run_once("pasystray")
	run_once("picom")
end

return M
