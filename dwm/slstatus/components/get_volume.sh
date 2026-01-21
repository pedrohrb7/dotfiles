#!/bin/bash

pactl get-sink-volume @DEFAULT_SINK@ | awk -F'/' '{print $2}'
