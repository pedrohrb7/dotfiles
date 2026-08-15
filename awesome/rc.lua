-- If LuaRocks is installed, make sure that packages installed through it are
-- found (e.g. lgi). If LuaRocks is not installed, do nothing.
pcall(require, "luarocks.loader")

-- Error handling
require("config.handle-errors")

require("awful.hotkeys_popup.keys")
require("awful.autofocus")

-- Standard awesome library
local gears = require("gears")
local awful = require("awful")
local wibox = require("wibox")
local beautiful = require("beautiful")
local menubar = require("menubar")
local naughty = require("naughty")

local calendar_widget = require("config.widgets.calendar")
local volume_widget = require("config.widgets.audio.volume")
local mic_widget = require("config.widgets.audio.mic")
local brightness_widget = require("config.widgets.brightness-widgets.brightness")
local battery_widget = require("config.widgets.battery")
-- local gpu_widget = require("config.widgets.gpu")
local cpu_widget = require("config.widgets.cpu")
-- local mem_widget = require("config.widgets.mem")
local theme_manager = require("config.theme-manager")

local dpi = require("beautiful.xresources").apply_dpi

beautiful.init(theme_manager.path_for(theme_manager.current()))

-- Notification configuration
naughty.config.defaults.border_width = dpi(3)
naughty.config.spacing = dpi(8)
naughty.config.padding = dpi(16)
naughty.config.defaults.margin = dpi(8)
naughty.config.defaults.timeout = 5
naughty.config.presets = {
	normal = {
		timeout = 4,
		fg = beautiful.color_red,
		bg = beautiful.border_normal,
		border_color = beautiful.color_green,
	},
	low = { timeout = 2, fg = beautiful.color_white, bg = beautiful.bg_focus, border_color = beautiful.color_green },
	critical = {
		border_width = 1,
		border_color = beautiful.color_red,
		fg = beautiful.border_normal,
		bg = beautiful.color_red,
		timeout = 0,
	},
}

local SUPER = "Mod4"
local ALT = "Mod1"
local terminal = "kitty"
local fileManager = "kitty --hold sh -c 'yazi'"
local browser = "vivaldi-stable"

beautiful.systray_icon_spacing = 8 -- Default SUPER.

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

-- Keyboard map indicator and switcher
local mykeyboardlayout = awful.widget.keyboardlayout()

local mytextclock = wibox.widget.textclock("   %H:%M:%S %p    %a, %d %b, %Y ", 1, "America/Sao_Paulo")

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

	awful.button({ SUPER }, 1, function(t)
		if client.focus then
			client.focus:move_to_tag(t)
		end
	end),

	awful.button({}, 3, awful.tag.viewtoggle),

	awful.button({ SUPER }, 3, function(t)
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

local function set_wallpaper(s)
	awful.spawn.with_shell("~/.fehbg", false)
end

-- Re-set wallpaper when a screen's geometry changes (e.g. different resolution)
screen.connect_signal("property::geometry", set_wallpaper)

awful.screen.connect_for_each_screen(function(s)
	-- Wallpaper
	set_wallpaper(s)

	-- local tags = { "1", "2", "3", "4", "5", "6", "7", "8", "9" }
	local tags = { " ", "A", "W", "E", "S", "O", "M", "E" }
	awful.tag(tags, s, awful.layout.layouts[1])

	-- Create a promptbox for each screen
	s.mypromptbox = awful.widget.prompt({
		bg = beautiful.color_bg_alt,
		fg = beautiful.color_green,
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

	-- Polybar replaces the native wibar. Kept in place (not deleted) behind
	-- this flag: false hides the wibar AND skips creating the systray
	-- widget, since instantiating it embeds the icons and claims the X11
	-- systray manager selection even if the wibar itself is invisible,
	-- which blocks polybar's own tray module from claiming it.
	local show_native_wibar = false

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

	local widget_container = function(widget_args)
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
				widget_container({ widget = mykeyboardlayout }),
				s.mypromptbox,
			},
		},
		{ -- Middle widget: shrink-wrapped to its content width, full wibar height, always centered
			widget_container({ widget = mytextclock }),
			halign = "center",
			fill_vertical = true,
			widget = wibox.container.place,
		},
		{ -- Right widgets
			layout = wibox.layout.fixed.horizontal(),
			spacing = wibar_group_spacing,
			widget_container({ widget = cpu_widget() }),
			-- widget_container({ widget = mem_widget() }),
			-- widget_container({ widget = gpu_widget }),
			widget_container({ widget = volume_widget }),
			widget_container({ widget = mic_widget }),
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

local globalkeys = gears.table.join(
	-- #############################################
	-- Keyboard layout switch (us/br), both registered as XKB groups by autostart.sh
	awful.key({ "Control", ALT }, "space", function()
		local layout_names = { [0] = "us", [1] = "br" }
		local group = (awesome.xkb_get_layout_group() + 1) % 2
		awesome.xkb_set_layout_group(group)
		naughty.notify({ title = "Keyboard layout", text = layout_names[group], timeout = 1.5 })
	end, { description = "switch keyboard layout", group = "custom" }),
	-- #############################################

	-- #############################################
	-- Theme switch
	awful.key({ SUPER }, "t", function()
		theme_manager.switch_next()
	end, { description = "switch theme", group = "awesome" }),
	-- #############################################

	-- #############################################
	-- Brightness widget
	awful.key({}, "XF86MonBrightnessUp", function()
		brightness_widget:inc()
	end, { description = "increase brightness", group = "custom" }),

	awful.key({}, "XF86MonBrightnessDown", function()
		brightness_widget:dec()
	end, { description = "decrease brightness", group = "custom" }),
	--
	-- Alternatively, keybindings to control brightness:
	awful.key({ SUPER, "Shift" }, "g", function()
		brightness_widget:inc()
	end),
	awful.key({ SUPER, "Shift" }, "f", function()
		brightness_widget:dec()
	end),
	-- #############################################

	-- #############################################
	-- Volume keys
	awful.key({}, "XF86AudioLowerVolume", function()
		awful.util.spawn("pamixer -d 5", false)
	end),
	awful.key({}, "XF86AudioRaiseVolume", function()
		awful.util.spawn("pamixer -i 5", false)
	end),
	awful.key({}, "XF86AudioMute", function()
		awful.util.spawn("pamixer -t", false)
	end),
	--
	-- #############################################

	-- #############################################
	-- Mic keys
	awful.key({ SUPER, "Shift" }, "o", function()
		awful.util.spawn("pamixer --default-source -t", false)
	end),
	awful.key({ SUPER, "Shift" }, "n", function()
		awful.util.spawn("pamixer --default-source -i 5", false)
	end),
	awful.key({ SUPER, "Shift" }, "b", function()
		awful.util.spawn("pamixer --default-source -d 5", false)
	end),
	--
	-- #############################################

	awful.key({}, "Print", function()
		awful.spawn("flameshot gui")
	end, { description = "take screenshot", group = "hotkeys" }),

	awful.key({ SUPER }, "Left", awful.tag.viewprev, { description = "view previous", group = "tag" }),
	awful.key({ SUPER }, "Right", awful.tag.viewnext, { description = "view next", group = "tag" }),
	awful.key({ SUPER }, "Escape", awful.tag.history.restore, { description = "go back", group = "tag" }),

	awful.key({ SUPER }, "j", function()
		awful.client.focus.byidx(1)
	end, { description = "focus next by index", group = "client" }),

	awful.key({ SUPER }, "k", function()
		awful.client.focus.byidx(-1)
	end, { description = "focus previous by index", group = "client" }),

	-- Layout manipulation
	awful.key({ SUPER, "Shift" }, "j", function()
		awful.client.swap.byidx(1)
	end, { description = "swap with next client by index", group = "client" }),

	awful.key({ SUPER, "Shift" }, "k", function()
		awful.client.swap.byidx(-1)
	end, { description = "swap with previous client by index", group = "client" }),

	awful.key({ SUPER }, "u", awful.client.urgent.jumpto, { description = "jump to urgent client", group = "client" }),

	awful.key({ SUPER }, "Tab", function()
		awful.client.focus.history.previous()
		if client.focus then
			client.focus:raise()
		end
	end, { description = "go back", group = "client" }),

	-- Standard program
	awful.key({ SUPER }, "Return", function()
		awful.spawn(terminal)
	end, { description = "open a terminal", group = "launcher" }),

	awful.key({ SUPER }, "b", function()
		awful.spawn(browser)
	end, { description = "open default browser", group = "launcher" }),

	awful.key({ SUPER }, "e", function()
		awful.spawn(fileManager)
	end, { description = "open nautilus", group = "launcher" }),

	-- Menubar
	awful.key({ SUPER }, "p", function()
		-- menubar.show()
		awful.spawn("rofi -show drun")
	end, { description = "show the menubar", group = "launcher" }),

	awful.key({ SUPER, "Control" }, "r", awesome.restart, { description = "reload awesome", group = "awesome" }),

	awful.key({ SUPER, "Shift" }, "q", awesome.quit, { description = "quit awesome", group = "awesome" }),

	awful.key({ SUPER }, "l", function()
		awful.tag.incmwfact(0.05)
	end, { description = "increase master width factor", group = "layout" }),

	awful.key({ SUPER }, "h", function()
		awful.tag.incmwfact(-0.05)
	end, { description = "decrease master width factor", group = "layout" }),

	awful.key({ SUPER, "Shift" }, "h", function()
		awful.tag.incnmaster(1, nil, true)
	end, { description = "increase the number of master clients", group = "layout" }),

	awful.key({ SUPER, "Shift" }, "l", function()
		awful.tag.incnmaster(-1, nil, true)
	end, { description = "decrease the number of master clients", group = "layout" }),

	awful.key({ SUPER, "Control" }, "h", function()
		awful.tag.incncol(1, nil, true)
	end, { description = "increase the number of columns", group = "layout" }),

	awful.key({ SUPER, "Control" }, "l", function()
		awful.tag.incncol(-1, nil, true)
	end, { description = "decrease the number of columns", group = "layout" }),

	awful.key({ SUPER }, "space", function()
		awful.layout.inc(1)
	end, { description = "select next", group = "layout" }),

	awful.key({ SUPER, "Shift" }, "space", function()
		awful.layout.inc(-1)
	end, { description = "select previous", group = "layout" }),

	awful.key({ SUPER, "Control" }, "n", function()
		local c = awful.client.restore()
		-- Focus restored client
		if c then
			c:emit_signal("request::activate", "key.unminimize", { raise = true })
		end
	end, { description = "restore minimized", group = "client" }),

	-- Prompt
	awful.key({ SUPER }, "r", function()
		awful.screen.focused().mypromptbox:run()
	end, { description = "run prompt", group = "launcher" }),

	awful.key({ SUPER }, "x", function()
		awful.prompt.run({
			prompt = "Run Lua code: ",
			textbox = awful.screen.focused().mypromptbox.widget,
			exe_callback = awful.util.eval,
			history_path = awful.util.get_cache_dir() .. "/history_eval",
		})
	end, { description = "lua execute prompt", group = "awesome" })
)

local clientkeys = gears.table.join(
	awful.key({ SUPER }, "f", function(c)
		c.fullscreen = not c.fullscreen
		c:raise()
	end, { description = "toggle fullscreen", group = "client" }),

	awful.key({ SUPER, "Shift" }, "c", function(c)
		c:kill()
	end, { description = "close", group = "client" }),

	awful.key(
		{ SUPER, "Control" },
		"space",
		awful.client.floating.toggle,
		{ description = "toggle floating", group = "client" }
	),

	awful.key({ SUPER, "Control" }, "Return", function(c)
		c:swap(awful.client.getmaster())
	end, { description = "move to master", group = "client" }),

	awful.key({ SUPER }, "o", function(c)
		c:move_to_screen()
	end, { description = "move to screen", group = "client" }),

	awful.key({ SUPER }, "n", function(c)
		-- The client currently has the input focus, so it cannot be
		-- minimized, since minimized clients can't have the focus.
		c.minimized = true
	end, { description = "minimize", group = "client" }),

	awful.key({ SUPER }, "m", function(c)
		c.maximized = not c.maximized
		c:raise()
	end, { description = "(un)maximize", group = "client" }),

	awful.key({ SUPER, "Control" }, "m", function(c)
		c.maximized_vertical = not c.maximized_vertical
		c:raise()
	end, { description = "(un)maximize vertically", group = "client" }),

	awful.key({ SUPER, "Shift" }, "m", function(c)
		c.maximized_horizontal = not c.maximized_horizontal
		c:raise()
	end, { description = "(un)maximize horizontally", group = "client" }),

	-- ###############################
	-- Send a test notification
	-- info at https://awesomewm.org/doc/api/libraries/naughty.html#notify
	awful.key({ SUPER, "Shift" }, "t", function()
		awful.spawn.with_shell([[
        action=$(dunstify "Test Title" "Test Notification" -A "change,Change" -u normal -b)
        if [ "$action" = "change" ]; then
            dunstify "CHANGE" "MUDA"
        fi
    ]])
		-- naughty.notify({
		-- 	title = "Test Title",
		-- 	text = "Test Notification",
		-- 	preset = naughty.config.presets.normal,
		-- 	-- actions = {
		-- 	-- change = awful.spawn.with_shell('dunstify "CHANGE" "MUDA"'),
		-- 	-- },
		--
		-- 	timeout = 0,
		-- 	actions = {
		-- 		change = naughty.action("Change"),
		-- 	},
		-- 	callback = function(notification, action)
		-- 		if action and action.name == "Change" then
		-- 			awful.spawn.with_shell('dunstify "CHANGE" "MUDA"')
		-- 			awful.spawn.with_shell("NOTIFY :: " .. notification)
		-- 		end
		-- 	end,
		-- })
	end, { description = "send test notification", group = "awesome" })
)

-- Bind all key numbers to tags.
-- Be careful: we use keycodes to make it work on any keyboard layout.
-- This should map on the top row of your keyboard, usually 1 to 9.
for i = 1, 9 do
	globalkeys = gears.table.join(
		globalkeys,
		-- View tag only.
		awful.key({ SUPER }, "#" .. i + 9, function()
			local screen = awful.screen.focused()
			local tag = screen.tags[i]
			if tag then
				tag:view_only()
			end
		end, { description = "view tag #" .. i, group = "tag" }),

		-- Toggle tag display.
		awful.key({ SUPER, "Control" }, "#" .. i + 9, function()
			local screen = awful.screen.focused()
			local tag = screen.tags[i]
			if tag then
				awful.tag.viewtoggle(tag)
			end
		end, { description = "toggle tag #" .. i, group = "tag" }),

		-- Move client to tag.
		awful.key({ SUPER, "Shift" }, "#" .. i + 9, function()
			if client.focus then
				local tag = client.focus.screen.tags[i]
				if tag then
					client.focus:move_to_tag(tag)
				end
			end
		end, { description = "move focused client to tag #" .. i, group = "tag" }),

		-- Toggle tag on focused client.
		awful.key({ SUPER, "Control", "Shift" }, "#" .. i + 9, function()
			if client.focus then
				local tag = client.focus.screen.tags[i]
				if tag then
					client.focus:toggle_tag(tag)
				end
			end
		end, { description = "toggle focused client on tag #" .. i, group = "tag" })
	)
end

local clientbuttons = gears.table.join(
	awful.button({}, 1, function(c)
		c:emit_signal("request::activate", "mouse_click", { raise = true })
	end),
	awful.button({ SUPER }, 1, function(c)
		c:emit_signal("request::activate", "mouse_click", { raise = true })
		awful.mouse.client.move(c)
	end),
	awful.button({ SUPER }, 3, function(c)
		c:emit_signal("request::activate", "mouse_click", { raise = true })
		awful.mouse.client.resize(c)
	end)
)

-- Set keys
root.keys(globalkeys)

awful.rules.rules = {
	{
		rule = {},
		properties = {
			border_width = beautiful.border_width,
			border_color = beautiful.border_normal,
			focus = awful.client.focus.filter,
			raise = true,
			keys = clientkeys,
			buttons = clientbuttons,
			screen = awful.screen.preferred,
			placement = awful.placement.no_overlap + awful.placement.no_offscreen,
		},
	},

	-- Floating clients.
	{
		rule_any = {
			instance = {
				"DTA", -- Firefox addon DownThemAll.
				"copyq", -- Includes session name in class.
				"pinentry",
			},
			class = {
				"Arandr",
				"Blueman-manager",
				"Gpick",
				"Kruler",
				"MessageWin", -- kalarm.
				"Sxiv",
				"Wpa_gui",
				"pavucontrol",
			},

			-- Note that the name property shown in xprop might be set slightly after creation of the client
			-- and the name shown there might not match defined rules here.
			name = {
				"Event Tester", -- xev.
			},
			role = {
				"AlarmWindow", -- Thunderbird's calendar.
				"ConfigManager", -- Thunderbird's about:config.
				"pop-up", -- e.g. Google Chrome's (detached) Developer Tools.
			},
		},
		properties = { floating = true },
	},

	-- Add titlebars to normal clients and dialogs
	{ rule_any = { type = { "normal", "dialog" } }, properties = { titlebars_enabled = false } },

	-- Set Firefox to always map on the tag named "2" on screen 1.
	-- { rule = { class = "Firefox" },
	--   properties = { screen = 1, tag = "2" } },
}
-- }}}

-- {{{ Signals
-- Signal function to execute when a new client appears.
client.connect_signal("manage", function(c)
	-- Set the windows at the slave,
	-- i.e. put it at the end of others instead of setting it master.
	-- if not awesome.startup then awful.client.setslave(c) end

	if awesome.startup and not c.size_hints.user_position and not c.size_hints.program_position then
		-- Prevent clients from being unreachable after screen count changes.
		awful.placement.no_offscreen(c)
	end
end)

-- Add a titlebar if titlebars_enabled is set to true in the rules.
client.connect_signal("request::titlebars", function(c)
	local buttons = gears.table.join(
		awful.button({}, 1, function()
			c:emit_signal("request::activate", "titlebar", { raise = true })
			awful.mouse.client.move(c)
		end),
		awful.button({}, 3, function()
			c:emit_signal("request::activate", "titlebar", { raise = true })
			awful.mouse.client.resize(c)
		end)
	)

	awful.titlebar(c):setup({
		{ -- Left
			awful.titlebar.widget.iconwidget(c),
			buttons = buttons,
			-- layout = wibox.layout.fixed.horizontal,
		},
		{ -- Middle
			{ -- Title
				align = "center",
				widget = awful.titlebar.widget.titlewidget(c),
			},
			buttons = buttons,
			-- layout = wibox.layout.flex.horizontal,
		},
		{ -- Right
			awful.titlebar.widget.floatingbutton(c),
			awful.titlebar.widget.maximizedbutton(c),
			awful.titlebar.widget.stickybutton(c),
			awful.titlebar.widget.ontopbutton(c),
			awful.titlebar.widget.closebutton(c),
			-- layout = wibox.layout.fixed.horizontal(),
		},
		-- layout = wibox.layout.align.horizontal,
	})
end)

-- Enable sloppy focus, so that focus follows mouse.
client.connect_signal("mouse::enter", function(c)
	c:emit_signal("request::activate", "mouse_enter", { raise = false })
end)

client.connect_signal("focus", function(c)
	c.border_color = beautiful.border_focus
end)

client.connect_signal("unfocus", function(c)
	c.border_color = beautiful.border_normal
end)

-- Autostart applications
awful.spawn.with_shell("~/.config/awesome/autostart.sh")
