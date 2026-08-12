-----------------------------------------
-- cyberawesome / neonpunk theme        --
-- Cyberpunk 2077 inspired: near-black  --
-- with neon yellow, cyan and magenta   --
-----------------------------------------

local theme_assets = require("beautiful.theme_assets")
local xresources = require("beautiful.xresources")
local dpi = xresources.apply_dpi
local gears = require("gears")

local gfs = require("gears.filesystem")
local themes_path = gfs.get_themes_dir()

local theme = {}

-- Palette
local bg = "#0d0d0f"
local bg_alt = "#1a1a20"
local fg = "#d8d8e0"
local accent1 = "#f6e100" -- neon yellow: focus/highlight
local accent2 = "#00f0ff" -- neon cyan: info/secondary
local accent3 = "#ff2079" -- neon magenta: urgent/alert
local border_dim = "#232329"

theme.font = "FiraCode Nerd Font 11"

theme.bg_normal = bg
theme.bg_focus = bg_alt
theme.bg_urgent = accent3
theme.bg_minimize = bg_alt
theme.bg_systray = theme.bg_normal

theme.fg_normal = fg
theme.fg_focus = accent1
theme.fg_urgent = bg
theme.fg_minimize = fg

theme.color_red = accent1
theme.color_green = accent2
theme.color_white = fg
theme.color_bg_alt = bg_alt

theme.useless_gap = dpi(6)
theme.border_width = dpi(1)
theme.border_normal = border_dim
theme.border_focus = accent1
theme.border_marked = accent3

-- Wibar
theme.wibar_height = dpi(34)
theme.wibar_bg = "#00000000"
theme.wibar_shape = function(cr, w, h)
	gears.shape.rounded_rect(cr, w, h, 8)
end
theme.wibar_spacing = dpi(10)
theme.wibar_group_spacing = dpi(8)
theme.wibar_widget_margin_lr = dpi(10)
theme.wibar_widget_margin_tb = dpi(4)
theme.wibar_widget_bg = bg_alt
theme.wibar_widget_shape = gears.shape.rounded_rect
theme.wibar_widget_border_width = dpi(1)
theme.wibar_widget_border_color = border_dim

-- Taglist
local taglist_square_size = dpi(4)
theme.taglist_fg_focus = accent1
theme.taglist_bg_focus = "#00000000"
theme.taglist_fg_occupied = accent2
theme.taglist_fg_empty = fg
theme.taglist_squares_sel = theme_assets.taglist_squares_sel(taglist_square_size, accent1)
theme.taglist_squares_unsel = theme_assets.taglist_squares_unsel(taglist_square_size, fg)

-- Notifications
theme.notification_font = "FiraCode Nerd Font 8"
theme.notification_bg = bg_alt
theme.notification_fg = fg

-- Menu
theme.menu_submenu_icon = themes_path .. "default/submenu.png"
theme.menu_height = dpi(30)
theme.menu_width = dpi(200)

-- Titlebar (stock icons)
theme.titlebar_close_button_normal = themes_path .. "default/titlebar/close_normal.png"
theme.titlebar_close_button_focus = themes_path .. "default/titlebar/close_focus.png"

theme.titlebar_minimize_button_normal = themes_path .. "default/titlebar/minimize_normal.png"
theme.titlebar_minimize_button_focus = themes_path .. "default/titlebar/minimize_focus.png"

theme.titlebar_ontop_button_normal_inactive = themes_path .. "default/titlebar/ontop_normal_inactive.png"
theme.titlebar_ontop_button_focus_inactive = themes_path .. "default/titlebar/ontop_focus_inactive.png"
theme.titlebar_ontop_button_normal_active = themes_path .. "default/titlebar/ontop_normal_active.png"
theme.titlebar_ontop_button_focus_active = themes_path .. "default/titlebar/ontop_focus_active.png"

theme.titlebar_sticky_button_normal_inactive = themes_path .. "default/titlebar/sticky_normal_inactive.png"
theme.titlebar_sticky_button_focus_inactive = themes_path .. "default/titlebar/sticky_focus_inactive.png"
theme.titlebar_sticky_button_normal_active = themes_path .. "default/titlebar/sticky_normal_active.png"
theme.titlebar_sticky_button_focus_active = themes_path .. "default/titlebar/sticky_focus_active.png"

theme.titlebar_floating_button_normal_inactive = themes_path .. "default/titlebar/floating_normal_inactive.png"
theme.titlebar_floating_button_focus_inactive = themes_path .. "default/titlebar/floating_focus_inactive.png"
theme.titlebar_floating_button_normal_active = themes_path .. "default/titlebar/floating_normal_active.png"
theme.titlebar_floating_button_focus_active = themes_path .. "default/titlebar/floating_focus_active.png"

theme.titlebar_maximized_button_normal_inactive = themes_path .. "default/titlebar/maximized_normal_inactive.png"
theme.titlebar_maximized_button_focus_inactive = themes_path .. "default/titlebar/maximized_focus_inactive.png"
theme.titlebar_maximized_button_normal_active = themes_path .. "default/titlebar/maximized_normal_active.png"
theme.titlebar_maximized_button_focus_active = themes_path .. "default/titlebar/maximized_focus_active.png"

-- Layout icons (stock)
theme.layout_fairh = themes_path .. "default/layouts/fairhw.png"
theme.layout_fairv = themes_path .. "default/layouts/fairvw.png"
theme.layout_floating = themes_path .. "default/layouts/floatingw.png"
theme.layout_magnifier = themes_path .. "default/layouts/magnifierw.png"
theme.layout_max = themes_path .. "default/layouts/maxw.png"
theme.layout_fullscreen = themes_path .. "default/layouts/fullscreenw.png"
theme.layout_tilebottom = themes_path .. "default/layouts/tilebottomw.png"
theme.layout_tileleft = themes_path .. "default/layouts/tileleftw.png"
theme.layout_tile = themes_path .. "default/layouts/tilew.png"
theme.layout_tiletop = themes_path .. "default/layouts/tiletopw.png"
theme.layout_spiral = themes_path .. "default/layouts/spiralw.png"
theme.layout_dwindle = themes_path .. "default/layouts/dwindlew.png"
theme.layout_cornernw = themes_path .. "default/layouts/cornernww.png"
theme.layout_cornerne = themes_path .. "default/layouts/cornernew.png"
theme.layout_cornersw = themes_path .. "default/layouts/cornersww.png"
theme.layout_cornerse = themes_path .. "default/layouts/cornersew.png"

theme.awesome_icon = theme_assets.awesome_icon(theme.menu_height, theme.bg_focus, theme.fg_focus)

theme.icon_theme = nil

return theme
