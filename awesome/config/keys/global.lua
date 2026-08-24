-- Global keybindings: launchers, tags, layout, client focus/swap, root binds.
local awful = require("awful")
local gears = require("gears")
local naughty = require("naughty")

local vars = require("config.vars")
local brightness_widget = require("config.widgets.brightness-widgets.brightness")

local SUPER = vars.SUPER
local ALT = vars.ALT
local terminal = vars.terminal
local fileManager = vars.fileManager
local browser = vars.browser

local globalkeys = gears.table.join(
	-- #############################################
	-- Keyboard layout switch (us/br), both registered as XKB groups by .xinitrc
	awful.key({ "Control", ALT }, "space", function()
		local layout_names = { [0] = "us", [1] = "br" }
		local group = (awesome.xkb_get_layout_group() + 1) % 2
		awesome.xkb_set_layout_group(group)
		naughty.notify({ title = "Keyboard layout", text = layout_names[group], timeout = 1.5 })
	end, { description = "switch keyboard layout", group = "custom" }),
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

return globalkeys
