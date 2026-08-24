-- Top wibar: tags, layoutbox, tasklist, clock/keyboardlayout/systray.
local gears = require("gears")
local awful = require("awful")
local wibox = require("wibox")
local beautiful = require("beautiful")
local dpi = require("beautiful.xresources").apply_dpi

local vars = require("config.vars")
local volume_widget = require("config.widgets.volume")
local mic_widget = require("config.widgets.mic")
local brightness_widget = require("config.widgets.brightness")
local bluetooth_widget = require("config.widgets.bluetooth")
local network_widget = require("config.widgets.network")

local M = {}

local function set_wallpaper(s)
	-- Wallpaper
	if beautiful.wallpaper then
		local wallpaper = beautiful.wallpaper
		-- If wallpaper is a function, call it with the screen
		if type(wallpaper) == "function" then
			wallpaper = wallpaper(s)
		end
		gears.wallpaper.maximized(wallpaper, s, true)
	end
end

function M.init()
	-- Table of layouts to cover with awful.layout.inc, order matters.
	awful.layout.layouts = vars.layouts

	local mykeyboardlayout = awful.widget.keyboardlayout()
	local mytextclock = wibox.widget.textclock("%a %b %d, %H:%M:%S", 1)

	local mycalendar = awful.widget.calendar_popup.month()
	mycalendar:attach(mytextclock, "tr")

	-- Left click = previous month, right click = next month (scroll still
	-- works too, that's the calendar_popup default).
	mycalendar:buttons(gears.table.join(
		awful.button({}, 1, function()
			mycalendar:call_calendar(-1)
		end),
		awful.button({}, 3, function()
			mycalendar:call_calendar(1)
		end),
		awful.button({}, 4, function()
			mycalendar:call_calendar(-1)
		end),
		awful.button({}, 5, function()
			mycalendar:call_calendar(1)
		end)
	))

	-- Some tray apps ignore the systray's size hint and render oversized
	-- icons; force a fixed base size so all icons match.
	local mysystray = wibox.widget.systray()
	mysystray:set_base_size(dpi(16))

	local myvolume = volume_widget({ step = 5, timeout = 2 })
	local mymic = mic_widget({ timeout = 2 })
	local mybrightness = brightness_widget({ step = 5, timeout = 2 })
	local mybluetooth = bluetooth_widget({ timeout = 5 })
	local mynetwork = network_widget({ timeout = 5 })

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

	local tasklist_buttons = gears.table.join(
		awful.button({}, 1, function(c)
			if c == client.focus then
				c.minimized = true
			else
				c:emit_signal("request::activate", "tasklist", { raise = true })
			end
		end),
		awful.button({}, 3, function()
			awful.menu.client_list({ theme = { width = 250 } })
		end),
		awful.button({}, 4, function()
			awful.client.focus.byidx(1)
		end),
		awful.button({}, 5, function()
			awful.client.focus.byidx(-1)
		end)
	)

	-- Re-set wallpaper when a screen's geometry changes (e.g. different resolution)
	screen.connect_signal("property::geometry", set_wallpaper)

	awful.screen.connect_for_each_screen(function(s)
		-- Wallpaper
		set_wallpaper(s)

		-- Each screen has its own tag table.
		local custom_tags = { " ", "A", "W", "E", "S", "O", "M", "E" }
		awful.tag(custom_tags, s, vars.layouts[1])

		-- Create a promptbox for each screen
		s.mypromptbox = awful.widget.prompt()

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

		-- Create a tasklist widget
		s.mytasklist = awful.widget.tasklist({
			screen = s,
			filter = awful.widget.tasklist.filter.currenttags,
			buttons = tasklist_buttons,
		})

		-- Create the wibox. bg/fg fall back to the library defaults
		-- (bg_normal/fg_normal) when theme.wibar_bg/wibar_fg aren't set.
		s.mywibox = awful.wibar({
			position = "top",
			screen = s,
			bg = beautiful.wibar_bg,
			fg = beautiful.wibar_fg,
		})

		-- Add widgets to the wibox
		s.mywibox:setup({
			layout = wibox.layout.align.horizontal,
			{ -- Left widgets
				layout = wibox.layout.fixed.horizontal,
				spacing = dpi(12),
				s.mytaglist,
				s.mypromptbox,
			},
			s.mytasklist, -- Middle widget
			{ -- Right widgets
				layout = wibox.layout.fixed.horizontal,
				spacing = dpi(12),
				mykeyboardlayout,
				mysystray,
				mynetwork,
				mybluetooth,
				mybrightness,
				mymic,
				myvolume,
				mytextclock,
				s.mylayoutbox,
			},
		})
	end)
end

return M
