-- Top wibar: tags, layoutbox, clock/calendar and the status widgets on the
-- right. This is the visible bar (polybar is no longer used).
local gears = require("gears")
local awful = require("awful")
local wibox = require("wibox")
local beautiful = require("beautiful")
local dpi = require("beautiful.xresources").apply_dpi

local vars = require("config.vars")
local calendar_widget = require("config.widgets.calendar")
local volume_widget = require("config.widgets.audio.volume")
local mic_widget = require("config.widgets.audio.mic")
local brightness_widget = require("config.widgets.brightness-widgets.brightness")
local battery_widget = require("config.widgets.battery")
local cpu_widget = require("config.widgets.cpu")
-- local gpu_widget = require("config.widgets.gpu")
-- local mem_widget = require("config.widgets.mem")

local M = {}

local function set_wallpaper()
	awful.spawn.with_shell("~/.fehbg", false)
end

local function widget_container(
	widget_args,
	wibar_widget_margin_lr,
	wibar_widget_margin_tb,
	wibar_widget_bg,
	wibar_widget_shape,
	wibar_widget_border_width,
	wibar_widget_border_color
)
	local args = widget_args or {}

	return wibox.widget({
		{
			args.widget,
			left = args.left or wibar_widget_margin_lr,
			right = args.right or wibar_widget_margin_lr,
			top = args.top or wibar_widget_margin_tb,
			bottom = args.bottom or wibar_widget_margin_tb,
			widget = wibox.container.margin,
		},
		bg = args.bg or wibar_widget_bg,
		shape = wibar_widget_shape,
		shape_border_width = wibar_widget_bg and wibar_widget_border_width or nil,
		shape_border_color = wibar_widget_bg and wibar_widget_border_color or nil,
		shape_clip = true,
		widget = wibox.container.background,
	})
end

function M.init()
	local mylauncher = awful.widget.launcher({ image = beautiful.awesome_icon })
	local mykeyboardlayout = awful.widget.keyboardlayout()
	local mytextclock = wibox.widget.textclock("   %H:%M:%S %p    %a, %d %b, %Y ", 1, "America/Sao_Paulo")

	local cw = calendar_widget({
		theme = "naughty",
		placement = "top_right",
		start_sunday = true,
		radius = 8,
		-- with customized next/previous (see table above)
		previous_month_button = 1,
		next_month_button = 3,
	})

	mytextclock:connect_signal("button::press", function(_, _, _, button)
		if button == 1 then
			cw.toggle()
		end
	end)

	local taglist_buttons = gears.table.join(
		awful.button({}, 1, function(t)
			t:view_only()
		end),

		awful.button({ vars.SUPER }, 1, function(t)
			if client.focus then
				client.focus:move_to_tag(t)
			end
		end),

		awful.button({}, 3, awful.tag.viewtoggle),

		awful.button({ vars.SUPER }, 3, function(t)
			if client.focus then
				client.focus:toggle_tag(t)
			end
		end),

		awful.button({}, 4, function(t)
			awful.tag.viewnext(t.screen)
		end),

		awful.button({}, 5, function(t)
			awful.tag.viewprev(t.screen)
		end)
	)

	-- Re-set wallpaper when a screen's geometry changes (e.g. different resolution)
	screen.connect_signal("property::geometry", set_wallpaper)

	awful.screen.connect_for_each_screen(function(s)
		-- Wallpaper
		set_wallpaper(s)

		-- local tags = { "1", "2", "3", "4", "5", "6", "7", "8", "9" }
		local tags = { " ", "A", "W", "E", "S", "O", "M", "E" }
		awful.tag(tags, s, vars.layouts[1])

		-- Create a promptbox for each screen
		s.mypromptbox = awful.widget.prompt({
			-- bg = beautiful.color_bg_alt,
			-- fg = beautiful.color_green,
			font = "FiraCode Nerd Font 10",
		})

		-- Create an imagebox widget which will contain an icon indicating which layout we're using.
		-- We need one layoutbox per screen.
		s.mylayoutbox = awful.widget.layoutbox(s)

		s.mylayoutbox:buttons(gears.table.join(
			awful.button({}, 1, function()
				awful.layout.inc(1)
			end),

			awful.button({}, 3, function()
				awful.layout.inc(-1)
			end),

			awful.button({}, 4, function()
				awful.layout.inc(1)
			end),

			awful.button({}, 5, function()
				awful.layout.inc(-1)
			end)
		))
		-- Create a taglist widget
		s.mytaglist = awful.widget.taglist({
			screen = s,
			filter = awful.widget.taglist.filter.all,
			buttons = taglist_buttons,
		})

		local show_native_wibar = true

		-- Wibar geometry/spacing, themeable via beautiful.wibar_*; falls back to
		-- the previous hardcoded values so themes that don't set them are
		-- unaffected.
		local wibar_height = beautiful.wibar_height or 28
		local wibar_bg = beautiful.wibar_bg
		local wibar_shape = beautiful.wibar_shape
		local wibar_border_width = beautiful.wibar_border_width or 0
		local wibar_border_color = beautiful.wibar_border_color or beautiful.border_normal
		local wibar_spacing = beautiful.wibar_spacing or 5
		local wibar_group_spacing = beautiful.wibar_group_spacing or 5
		local wibar_widget_margin_lr = beautiful.wibar_widget_margin_lr or 0
		local wibar_widget_margin_tb = beautiful.wibar_widget_margin_tb or 2
		local wibar_widget_bg = beautiful.wibar_widget_bg
		local wibar_widget_shape = beautiful.wibar_widget_shape
		local wibar_widget_border_width = beautiful.wibar_widget_border_width
		local wibar_widget_border_color = beautiful.wibar_widget_border_color

		local function container(widget_args)
			return widget_container(
				widget_args,
				wibar_widget_margin_lr,
				wibar_widget_margin_tb,
				wibar_widget_bg,
				wibar_widget_shape,
				wibar_widget_border_width,
				wibar_widget_border_color
			)
		end

		-- Create the wibox
		s.mywibox = awful.wibar({
			height = wibar_height,
			position = "top",
			screen = s,
			bg = wibar_bg,
			shape = wibar_shape,
			border_width = wibar_border_width,
			border_color = wibar_border_color,
		})

		local mysystray = show_native_wibar and wibox.widget.systray() or nil
		if mysystray then
			mysystray:set_base_size(beautiful.wibar_systray_icon_size or dpi(16))
		end

		-- Add widgets to the wibox
		s.mywibox:setup({
			layout = wibox.layout.align.horizontal,
			spacing = wibar_spacing,
			{ -- Left widgets
				layout = wibox.layout.fixed.horizontal,
				spacing = wibar_group_spacing,
				{ -- Left widgets
					layout = wibox.layout.fixed.horizontal,
					s.mylayoutbox,
					mylauncher,
					s.mytaglist,
					container({ widget = mykeyboardlayout }),
					s.mypromptbox,
				},
			},
			{ -- Middle widget: shrink-wrapped to its content width, full wibar height, always centered
				container({ widget = mytextclock }),
				halign = "center",
				fill_vertical = true,
				widget = wibox.container.place,
			},
			{ -- Right widgets
				layout = wibox.layout.fixed.horizontal(),
				spacing = wibar_group_spacing,
				container({ widget = cpu_widget() }),
				-- container({ widget = mem_widget() }),
				-- container({ widget = gpu_widget }),
				container({ widget = volume_widget }),
				container({ widget = mic_widget }),
				container({
					widget = brightness_widget({
						type = "icon_and_text",
						program = "brightnessctl",
						step = 2,
						percentage = true,
						margin_left = 10,
						margin_right = 10,
					}),
				}),
				container({
					widget = battery_widget({
						show_current_level = true,
						margin_left = 10,
						margin_right = 10,
						display_notification = true,
					}),
				}),
				mysystray and {
					mysystray,
					valign = "center",
					widget = wibox.container.place,
				} or nil,
			},
		})

		s.mywibox.visible = show_native_wibar
	end)

	root.buttons(gears.table.join(awful.button({}, 4, awful.tag.viewnext), awful.button({}, 5, awful.tag.viewprev)))
end

return M
