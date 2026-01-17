-- If LuaRocks is installed, make sure that packages installed through it are
-- found (e.g. lgi). If LuaRocks is not installed, do nothing.
pcall(require, "luarocks.loader")

-- Error handling
require("configs.handle-errors")
-- Enable hotkeys help widget for VIM and other apps
-- when client with a matching name is opened:
require("awful.hotkeys_popup.keys")
require("awful.autofocus")

-- Standard awesome library
local gears = require("gears")
local awful = require("awful")
local cairo = require("lgi").cairo
local surface = cairo.ImageSurface(cairo.Format.ARGB32, 200, 50)
local cr = cairo.Context(surface)

-- Widget and layout library
local wibox = require("wibox")

-- Theme handling library
local beautiful = require("beautiful")

local menubar = require("menubar")
local hotkeys_popup = require("awful.hotkeys_popup")

-- Import custom widgets
local calendar_widget = require("configs.widgets.calendar")
local volume_widget = require("configs.widgets.audio.volume")
local cpu_widget = require("configs.widgets.cpu")
local brightness_widget = require("configs.widgets.brightness-widgets.brightness")
local battery_widget = require("configs.widgets.battery")
local theme = require("themes.default.theme")
local color = require("configs.color")
local gpu_widget = require("configs.widgets.gpu")
local mem_widget = require("configs.widgets.mem")

local modkey = "Mod4"
local terminal = "kitty"
local fileManager = "nautilus"

beautiful.init("~/.config/awesome/themes/default/theme.lua")
beautiful.bg_systray = theme.bg_focus
beautiful.systray_icon_spacing = 8
beautiful.menubar_bg_normal = color.magenta
beautiful.menubar_fg_normal = color.black

-- Table of layouts to cover with awful.layout.inc, order matters.
awful.layout.layouts = {
	awful.layout.suit.tile,
	awful.layout.suit.floating,
	awful.layout.suit.tile.left,
	awful.layout.suit.tile.bottom,
	awful.layout.suit.tile.top,
	awful.layout.suit.spiral,
	awful.layout.suit.spiral.dwindle,
	awful.layout.suit.max,
	awful.layout.suit.max.fullscreen,
}

local mylauncher = awful.widget.launcher({ image = beautiful.awesome_icon })

-- Menubar configuration
menubar.utils.terminal = terminal -- Set the terminal for applications that require it
-- }}}

-- Keyboard map indicator and switcher
local mykeyboardlayout = awful.widget.keyboardlayout()

-- {{{ Wibar
-- Create a textclock widget
-- local mytextclock = wibox.widget.textclock()
-- local mytextclock = wibox.widget.textclock()
local mytextclock = wibox.widget.textclock("   %H:%M:%S %p  %a, %d %b, %Y ", 1, "America/Sao_Paulo")

-- or customized
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

-- Create a wibox for each screen and add it
local taglist_buttons = gears.table.join(
	awful.button({}, 1, function(t)
		t:view_only()
	end),

	awful.button({ modkey }, 1, function(t)
		if client.focus then
			client.focus:move_to_tag(t)
		end
	end),

	awful.button({}, 3, awful.tag.viewtoggle),

	awful.button({ modkey }, 3, function(t)
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

-- Re-set wallpaper when a screen's geometry changes (e.g. different resolution)
-- awful.screen.connect_signal("property::geometry", set_wallpaper)

awful.screen.connect_for_each_screen(function(s)
	-- Wallpaper
	set_wallpaper(s)

	-- Each screen has its own tag table.
	-- local tagNames = { "1", "2", "3", "4", "5", "6", "7", "8", "9" }
	-- awful.tag(tagNames, s, awful.layout.layouts[1])
	local tagPacman = { " 󰮯 ", " 󰊠 ", " 󰊠 ", " 󰊠 ", " 󰊠 ", " 󰊠 ", " 󰊠 ", " 󰊠 ", " 󰊠 " }
	awful.tag(tagPacman, s, awful.layout.layouts[1])

	-- Create a promptbox for each screen
	s.mypromptbox = awful.widget.prompt({
		bg = color.background_lighter,
		fg = color.green,
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

	-- Create a tasklist widget
	s.mytasklist = awful.widget.tasklist({
		screen = s,
		filter = awful.widget.tasklist.filter.currenttags,
		buttons = tasklist_buttons,
	})

	-- Create the wibox
	s.mywibox = awful.wibar({ height = 28, position = "top", screen = s })

	local widget_container = function(widget_args)
		local args = widget_args or {}

		return wibox.widget({
			{
				args.widget,
				-- left = args.left or 10,
				top = args.top or 2,
				bottom = args.bottom or 2,
				-- right = args.right or 10,
				widget = wibox.container.margin,
			},
			bg = args.bg or theme.bg_focus,
			-- shape = args.shape or gears.shape.rounded_bar,
			shape_clip = true,
			widget = wibox.container.background,

			right = args.right or 10,
			left = args.left or 10,
			top = args.top or 2,
			bottom = args.bottom or 2,
		})
	end

	-- Add widgets to the wibox
	s.mywibox:setup({
		layout = wibox.layout.align.horizontal,
		spacing = 5,
		{ -- Left widgets
			layout = wibox.layout.fixed.horizontal,
			spacing = 5,
			{ -- Left widgets
				layout = wibox.layout.fixed.horizontal,
				mylauncher,
				s.mytaglist,
				s.mypromptbox,
			},
		},
		s.mytasklist, -- Middle widget
		{ -- Right widgets
			layout = wibox.layout.fixed.horizontal(),
			spacing = 5,
			widget_container({ widget = mykeyboardlayout }),
			-- widget_container({ widget = volume_widget }),
			widget_container({ widget = cpu_widget() }),
			widget_container({ widget = mem_widget() }),
			widget_container({ widget = gpu_widget }),
			widget_container({
				widget = brightness_widget({
					type = "icon_and_text",
					program = "brightnessctl",
					step = 2,
					percentage = true,
					margin_left = 10,
					margin_right = 10,
				}),
			}),
			widget_container({
				widget = battery_widget({
					show_current_level = true,
					margin_left = 10,
					margin_right = 10,
					display_notification = true,
				}),
			}),
			widget_container({ widget = mytextclock }),
			wibox.widget.systray(),
			s.mylayoutbox,
		},
	})
end)
-- }}}
