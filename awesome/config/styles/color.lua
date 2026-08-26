local color = {
	transparent = "#00000000",

	-- Backgrounds, darkest to lightest.
	background_dark = "#1a1b26",
	background_lighter = "#24283b",
	background_lightest = "#36424c",

	-- Base palette.
	white = "#ffffff",
	black = "#000000",
	gray_lighter = "#a9b1d6",
	light_blue = "#89b4fa",
	red = "#F7768E",
	green = "#73daca",
	yellow = "#E0AF68",
	blue = "#7AA2F7",
	magenta = "#BB9AF7",
	cyan = "#7dcfff",
	slate = "#2f404d",
	teal = "#85ebd9",
	dark_red = "#91231c",
}

color.primary = color.magenta
color.secondary = color.blue

color.border_color = color.slate
color.border_focus = color.teal
color.border_marked = color.dark_red

return color
