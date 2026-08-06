#!/usr/bin/env bash

setxkbmap -layout us,br

function run {
  if ! pgrep $1 ;
  then
    $@&
  fi
}

run "nm-applet"
run "blueman-applet"
run "pasystray"
