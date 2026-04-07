#!/usr/bin/env bash

function run {
  if ! pgrep $1 ;
  then
    $@&
  fi
}

run "pipewire"
run "nm-applet"
run "pasystray"
