-- Keyboard layouts (us/br) as XKB groups. The server default comes from
-- /etc/X11/xorg.conf.d/00-keyboard.conf (XkbLayout "us,br"), but the LightDM
-- greeter's layout indicator replaces the keymap with a single layout before the
-- session starts, which turns the layout switch into a no-op. ensure() restores
-- every group whenever the active keymap is missing one.
local awful = require("awful")
local naughty = require("naughty")

local M = {}

M.layouts = { "us", "br" }

-- Symbols look like "pc+us+br:2+inet(evdev)": the Nth group carries a ":N" suffix
local function has_all_groups()
	local symbols = awesome.xkb_get_group_names() or ""
	return #M.layouts < 2 or symbols:find(":" .. #M.layouts, 1, true) ~= nil
end

function M.ensure()
	if not has_all_groups() then
		awful.spawn({ "setxkbmap", "-layout", table.concat(M.layouts, ",") }, false)
	end
end

function M.toggle()
	awesome.xkb_set_layout_group((awesome.xkb_get_layout_group() + 1) % #M.layouts)
	-- Read back the active group: the switch is a no-op when only one layout is loaded
	local group = awesome.xkb_get_layout_group()
	naughty.notify({ title = "Keyboard layout", text = M.layouts[group + 1] or tostring(group), timeout = 1.5 })
end

function M.init()
	M.ensure()
	awesome.connect_signal("xkb::map_changed", M.ensure)
end

return M
