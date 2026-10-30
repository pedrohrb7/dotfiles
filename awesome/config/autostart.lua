-- Autostart: launches tray/compositor helpers, guarding each against
-- duplicate instances across awesome restarts (theme switch, etc).
local awful = require("awful")

local M = {}

local function run_once(prog, cmd)
	cmd = cmd or prog
	awful.spawn.with_shell(string.format("pgrep -u $USER -x %s > /dev/null || (%s)", prog, cmd))
end

-- PipeWire is up when its socket exists, not when the process does: a pipewire
-- left over from a previous session keeps running after elogind recreates
-- $XDG_RUNTIME_DIR, without a socket, so nothing can connect to it. In that
-- case it is replaced. On Void, pipewire itself starts wireplumber and
-- pipewire-pulse (/etc/pipewire/pipewire.conf.d); Artix ships its own launcher.
local PIPEWIRE = [[
[ -S "$XDG_RUNTIME_DIR/pipewire-0" ] && exit
pkill -u "$USER" -x wireplumber; pkill -u "$USER" -x pipewire
if command -v artix-pipewire-launcher > /dev/null; then exec artix-pipewire-launcher; fi
exec pipewire]]

function M.init()
	-- Screen layout: the autorandr profile matching the connected monitors
	-- (~/.config/autorandr), or all of them side by side when none matches. X
	-- falls back to the monitor's preferred mode (1024x768 on DP-1) otherwise.
	-- Hotplug is handled by autorandr's udev rule, which runs the same command.
	awful.spawn.with_shell("command -v autorandr > /dev/null && autorandr --change --default default")
	awful.spawn.with_shell(PIPEWIRE)
	run_once("picom")
	-- Only if installed, so a machine without conky doesn't log an error.
	run_once("conky", "command -v conky > /dev/null && conky --daemonize --pause=2")
end

return M
