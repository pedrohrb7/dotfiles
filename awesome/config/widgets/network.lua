-- Network widget: plain text (via nmcli), same style as the other widgets,
-- instead of relying on nm-applet's systray icon. Shows wifi (with SSID)
-- and wired connection status.
local awful = require("awful")
local wibox = require("wibox")
local watch = require("awful.widget.watch")

local M = {}

local function worker(args)
	args = args or {}
	local timeout = args.timeout or 5

	local widget = wibox.widget({
		id = "txt",
		widget = wibox.widget.textbox,
	})

	local eth_icon = "\u{f1e6}" -- plug
	local wifi_icon = "\u{f1eb}" -- wifi

	local function update(_, stdout)
		local eth_connected = false
		local wifi_connected = false
		local eth_name = nil
		local ssid = nil

		for line in stdout:gmatch("[^\r\n]+") do
			local dev_type, state, connection = line:match("^([^:]*):([^:]*):(.*)$")
			if dev_type == "ethernet" and state:match("^connected") then
				eth_connected = true
				eth_name = connection
			elseif dev_type == "wifi" and state:match("^connected") then
				wifi_connected = true
				ssid = connection
			end
		end

		local parts = {}
		if eth_connected then
			table.insert(parts, eth_icon .. " " .. eth_name)
		end
		if wifi_connected then
			table.insert(parts, wifi_icon .. " " .. ssid)
		end

		widget:set_text(table.concat(parts, "  "))
	end

	widget:buttons(awful.util.table.join(awful.button({}, 1, function()
		awful.spawn("nm-connection-editor", false)
	end)))

	watch("nmcli -t -f TYPE,STATE,CONNECTION device status", timeout, update, widget)

	return widget
end

return setmetatable(M, {
	__call = function(_, ...)
		return worker(...)
	end,
})
