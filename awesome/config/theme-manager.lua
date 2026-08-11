local awful = require("awful")
local gears = require("gears")

local M = {}

M.themes_dir = awful.util.get_configuration_dir() .. "config/themes/"
M.state_file = os.getenv("HOME") .. "/.aw-theme"
M.default_theme = "default"

function M.list()
	local themes = {}
	local handle = io.popen('ls -1 "' .. M.themes_dir .. '"')
	if not handle then
		return { M.default_theme }
	end

	for name in handle:lines() do
		if gears.filesystem.file_readable(M.themes_dir .. name .. "/theme.lua") then
			table.insert(themes, name)
		end
	end
	handle:close()

	table.sort(themes)

	if #themes == 0 then
		return { M.default_theme }
	end

	return themes
end

function M.current()
	local file = io.open(M.state_file, "r")
	if not file then
		return M.default_theme
	end

	local name = file:read("l")
	file:close()

	if not name then
		return M.default_theme
	end

	name = name:gsub("%s+", "")

	for _, theme in ipairs(M.list()) do
		if theme == name then
			return name
		end
	end

	return M.default_theme
end

function M.path_for(name)
	return M.themes_dir .. name .. "/theme.lua"
end

function M.save(name)
	local file = io.open(M.state_file, "w")
	if not file then
		return
	end
	file:write(name)
	file:close()
end

function M.next()
	local themes = M.list()
	local current = M.current()

	for i, theme in ipairs(themes) do
		if theme == current then
			return themes[(i % #themes) + 1]
		end
	end

	return themes[1]
end

function M.switch_next()
	M.save(M.next())
	awesome.restart()
end

return M
