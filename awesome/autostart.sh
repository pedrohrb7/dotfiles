#!/usr/bin/env bash

function run {
  if ! pgrep $1 ;
  then
    $@&
  fi
}

# run picom
# run conky
run pasystray
run blueman-applet
run nm-applet
run optimus-manager
run flameshot
run /usr/bin/lxpolkit
run "nitrogen --restore"

