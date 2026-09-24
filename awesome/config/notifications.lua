-- Notification (naughty) configuration: borders, spacing and presets.
local naughty = require("naughty")
local beautiful = require("beautiful")
local dpi = require("beautiful.xresources").apply_dpi
local awful = require("awful")
local gears = require("gears")

naughty.config.defaults.border_width = dpi(2)
naughty.config.spacing = dpi(8)
naughty.config.padding = dpi(16)
naughty.config.defaults.margin = dpi(8)
naughty.config.defaults.timeout = 5

local MIN_HEIGHT = dpi(72)
local ICON_WIDTH = dpi(360)
local ICON_MAX_HEIGHT = dpi(140)

naughty.config.presets = {
	normal = {
		timeout = 4,
	},
	low = {
		timeout = 2,
		fg = beautiful.wibar_fg,
		bg = beautiful.bg_normal,
		border_color = beautiful.border_normal,
	},
	critical = {
		timeout = 0,
		fg = beautiful.color_white,
		bg = beautiful.color_red,
		border_color = beautiful.border_marked,
	},
}

local function fix_action_buttons(notification, actions)
	local completelayout = notification.box.widget
	local actionslayout = completelayout:get_children()[2]
	if not actionslayout then
		return
	end

	for _, actionmarginbox in ipairs(actionslayout:get_children()) do
		local actiontextbox = actionmarginbox:get_children()[1]
		local markup = actiontextbox:get_markup()

		for label, callback in pairs(actions) do
			if markup == string.format("☛ <u>%s</u>", label) then
				actionmarginbox:buttons(gears.table.join(
					awful.button({}, 1, callback),
					awful.button({}, 3, function()
						notification.die(naughty.notificationClosedReason.dismissedByUser)
					end)
				))
			end
		end
	end
end

local function apply_default_size(args)
	if not args.icon then
		return
	end
	args.width = args.width or ICON_WIDTH
	args.max_height = args.max_height or ICON_MAX_HEIGHT
end

local function enforce_min_height(notification)
	if notification.height >= MIN_HEIGHT then
		return
	end
	local delta = MIN_HEIGHT - notification.height
	local geometry = notification.box:geometry()
	local y = geometry.y
	if not notification.position:match("top") then
		y = y - delta
	end
	notification.box:geometry({ y = y, height = MIN_HEIGHT })
	notification.height = MIN_HEIGHT
end

local notify = naughty.notify
naughty.notify = function(args)
	args = args or {}
	apply_default_size(args)

	local notification = notify(args)
	if not notification then
		return notification
	end

	if args.actions then
		fix_action_buttons(notification, args.actions)
	end
	enforce_min_height(notification)

	return notification
end
