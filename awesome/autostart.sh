#!/bin/bash

function run {
	if ! pgrep $1 ;
	then
		$@&
	fi
}

run "nitrogen --restore"
run "xscreensaver --no-splash"
run "picom"
run "nm-applet"
