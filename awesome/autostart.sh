#!/usr/bin/env bash

function run {
  if ! pgrep $1 ;
  then
    $@&
  fi
}

run "nm-applet"
run "blueman-applet"
run "pasystray"
