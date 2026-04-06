#!/usr/bin/env bash

function run {
  if ! pgrep $1 ;
  then
    $@&
  fi
}

run "pipewire"
run "wireplumber"
run "blueman-applet"
run "nm-applet"
run "flameshot"
run "dunst"
run "pasystray"

