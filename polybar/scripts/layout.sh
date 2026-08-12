#!/usr/bin/env bash

layout=$(echo 'local awful = require("awful"); return awful.layout.getname(awful.layout.get(awful.screen.focused()))' \
	| awesome-client 2>/dev/null \
	| sed -E 's/^[[:space:]]*string "(.*)"$/\1/')

echo "LAYOUT[${layout:-?}]"
