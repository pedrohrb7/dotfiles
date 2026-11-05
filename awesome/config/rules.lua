-- Client placement/floating rules (awful.rules.rules).
local awful = require("awful")
local beautiful = require("beautiful")

-- Applied to every client via the default rule
local clientkeymaps = require("config.keys.client")

return {
	{
		rule = {},
		properties = {
			border_width = beautiful.border_width,
			border_color = beautiful.border_normal,
			focus = awful.client.focus.filter,
			raise = true,
			keys = clientkeymaps.clientkeys,
			buttons = clientkeymaps.clientbuttons,
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
				"Nm-connection-editor",
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

	-- Polybar's calendar popup (scripts/calendar.sh): float it just below
	-- the bar, horizontally centered, instead of wherever no_overlap picks.
	{
		rule = { class = "Yad", name = "Calendar" },
		properties = {
			floating = true,
			ontop = true,
			skip_taskbar = true,
			placement = function(c)
				awful.placement.top(c, { honor_workarea = true, margins = { top = 4 } })
			end,
		},
	},

	-- Conky (~/dotfiles/conky): part of the desktop, not a regular window.
	-- Visible on every tag, kept below everything, never focused, no border,
	-- out of the tasklist, and left where conky positions itself.
	-- It also belongs to no tag (sticky alone keeps it visible), otherwise the
	-- taglist shows the tag it was mapped on as occupied. awful re-tags clients
	-- left without tags (after the rules, on screen changes), hence the signal.
	{
		rule = { class = "Conky" },
		properties = {
			border_width = 0,
			sticky = true,
			below = true,
			focusable = false,
			skip_taskbar = true,
			placement = function() end,
		},
		callback = function(c)
			c:tags({})
			c:connect_signal("tagged", function()
				c:tags({})
			end)
		end,
	},

	-- Add titlebars to normal clients and dialogs
	{ rule_any = { type = { "normal", "dialog" } }, properties = { titlebars_enabled = false } },

	-- Set Firefox to always map on the tag named "2" on screen 1.
	-- { rule = { class = "Firefox" },
	--   properties = { screen = 1, tag = "2" } },
}
