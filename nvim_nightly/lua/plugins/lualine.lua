vim.pack.add({
	{ src = "https://github.com/nvim-lualine/lualine.nvim" },
	{ src = "https://github.com/nvim-tree/nvim-web-devicons" },
})

local luaLine = require("lualine")
local trouble = require("trouble")

local symbols = trouble.statusline({
	mode = "lsp_document_symbols",
	groups = {},
	title = false,
	filter = { range = true },
	format = "{kind_icon}{symbol.name:Normal}",
	hl_group = "lualine_c_normal",
})

-- Config
local config = {
	options = {
		icons_enabled = true,
		disabled_filetypes = {
			statusline = { "neo-tree", "alpha" },
		},
		-- theme = {
		-- 	normal = {
		-- 		a = { fg = colors.color3, bg = colors.color1, gui = "bold" },
		-- 		b = { fg = colors.white, bg = colors.color1 },
		-- 		c = { fg = colors.purple, bg = colors.color1 },
		-- 	},
		-- 	insert = { a = { fg = colors.white, bg = colors.agua, gui = "bold" } },
		-- 	visual = { a = { fg = colors.white, bg = colors.purple, gui = "bold" } },
		-- 	replace = { a = { fg = colors.white, bg = colors.red, gui = "bold" } },
		-- 	inactive = {
		-- 		a = { fg = colors.silver, bg = colors.color1, gui = "bold" },
		-- 		b = { fg = colors.gray, bg = colors.color1 },
		-- 		c = { fg = colors.silver, bg = colors.color1 },
		-- 	},
		-- },
		-- section_separators = { left = "", right = "" },
		component_separators = "",
		section_separators = "",
	},
	sections = {
		-- lualine_a = { { "mode", icon = "  ", separator = { left = "" }, right_padding = 2 } },
		lualine_a = { { "mode", icon = "  ", separator = { left = "" }, right_padding = 2 } },
		lualine_b = { "filename", "branch", "diff" },
		lualine_c = { symbols.get },
		lualine_x = {},
		lualine_y = { "diagnostics", "filetype", "progress" },
		lualine_z = {
			-- { "location", separator = { right = "" }, left_padding = 2 },
			{ "location", separator = { right = "" }, left_padding = 2 },
		},
	},
	inactive_sections = {
		lualine_a = { "filename" },
		lualine_b = {},
		lualine_c = {},
		lualine_x = {},
		lualine_y = {},
		lualine_z = { "filetype" },
	},
	tabline = {},
	extensions = {},
}

luaLine.setup(config)
