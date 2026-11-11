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

local FILE_MANAGER_DESKTOP = "org.gnome.Nautilus.desktop"

function M.init()
	-- Screen layout (autorandr). Later plugs and unplugs are handled by
	-- config/screens.lua, which runs the same command.
	require("config.screens").apply_layout()
	awful.spawn.with_shell(PIPEWIRE)
	run_once("picom")
	-- Folders (xdg-open, "open folder" in other apps) go to Nautilus. Without
	-- this, the system mimeinfo.cache picks kitty-open.desktop first and opens a
	-- terminal. Written to ~/.config/mimeapps.list only when it differs.
	awful.spawn.with_shell(string.format(
		'command -v nautilus > /dev/null && [ "$(xdg-mime query default inode/directory)" != %s ] && xdg-mime default %s inode/directory',
		FILE_MANAGER_DESKTOP,
		FILE_MANAGER_DESKTOP
	))
	-- One conky per column (~/dotfiles/conky/right.conf and left.conf), each
	-- checked by its own config, so an awesome restart brings back only the one
	-- that is missing. "^conky" keeps pgrep from matching this shell's command
	-- line. Only if installed, so a machine without conky doesn't log an error.
	for _, conf in ipairs({ "right.conf", "left.conf" }) do
		awful.spawn.with_shell(string.format(
			'command -v conky > /dev/null && { pgrep -u "$USER" -f "^conky -c [^ ]*/%s" > /dev/null || conky -c "$HOME/.config/conky/%s" --daemonize --pause=2; }',
			conf,
			conf
		))
	end
end

return M
