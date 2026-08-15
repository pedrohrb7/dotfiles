#!/usr/bin/env bash

group=$(echo 'return tostring(awesome.xkb_get_layout_group())' \
	| awesome-client 2>/dev/null \
	| sed -E 's/^[[:space:]]*string "(.*)"$/\1/')

case "$group" in
0) kb="us" ;;
1) kb="br" ;;
*) kb="?" ;;
esac

echo "KB[${kb^^}]"
