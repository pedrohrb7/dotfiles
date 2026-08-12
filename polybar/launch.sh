#!/usr/bin/env bash

# Terminate already running bar instances
pkill -u "$UID" -x polybar

# Wait until the processes have been shut down
while pgrep -u "$UID" -x polybar >/dev/null; do sleep 1; done

polybar main -c "$HOME/.config/polybar/config.ini" &
