#!/bin/zsh

function run {
	if ! pgrep $1 ;
	then
		$@&
	fi
}

run "nitrogen --restore"
# run "xscreensaver --no-splash"
run "picom -b -f --config $HOME/.config/picom/picom.conf"
run "nm-applet"
