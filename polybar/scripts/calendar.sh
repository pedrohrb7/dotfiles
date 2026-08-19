#!/usr/bin/env bash
# Toggles a yad calendar popup near the polybar date module.
# Click again (or unfocus) closes it; the yad calendar widget already
# supports navigating between months with its built-in arrows.

PIDFILE="/tmp/polybar-calendar.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
	kill "$(cat "$PIDFILE")"
	rm -f "$PIDFILE"
	exit 0
fi

yad --calendar \
	--title="Calendar" \
	--no-buttons \
	--close-on-unfocus \
	--undecorated \
	--fixed &

echo $! >"$PIDFILE"
