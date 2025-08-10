-- --------------------------------------------
-- Volume widget for Awesome WM
-- Shows volume level
--
-- @author Pedro Borges
--
-- Highly inspired by this widget code
-- https://github.com/streetturtle/awesome-wm-widgets/tree/master/brightness-widget
-- @author Pavel Makhov
-- @copyright 2021 Pavel Makhov
-- --------------------------------------------

local awful = require("awful")
local wibox = require("wibox")
local watch = require("awful.widget.watch")
local spawn = require("awful.spawn")
local gfs = require("gears.filesystem")
local naughty = require("naughty")
local beautiful = require("beautiful")

local get_volume_cmd
local dec_volume_cmd
local inc_volume_cmd
local tog_volume_cmd

local volume_widget = {}

local function show_warning(message)
	naughty.notify({
		preset = naughty.config.presets.critical,
		title = "Volume Widget",
		text = message,
	})
end

local function worker(user_args)
	local args = user_args or {}

	local widget_text = args.text or " 󰖀 "
	local font = args.font or beautiful.font
	local timeout = args.timeout or 100
	local size = args.size or 18

	local step = args.step or 5
	local base = args.base or 20
	local current_level = 0

	local program = args.program or "pamixer"

	if program == "pactl" then
		get_volume_cmd = "pactl get-sink-volume @DEFAULT_SINK@"
	elseif program == "pamixer" then
		get_volume_cmd = "pamixer --get-volume-human"
		inc_volume_cmd = "pamixer -i" .. step
		dec_volume_cmd = "pamixer -d" .. step
	else
		show_warning(program .. " command is not supported by the widget")
		return
	end
end
