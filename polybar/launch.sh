#!/usr/bin/env bash

killall polybar
while pgrep -u $UID -x polybar >/dev/null; do sleep 1; done

CONFIG_DIR=$HOME/dotfiles-config/window-manager/polybar/custom/config.ini
polybar -c $CONFIG_DIR &
