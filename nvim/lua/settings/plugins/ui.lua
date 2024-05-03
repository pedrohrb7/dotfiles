return {
	-- the colorscheme should be available when starting Neovim
	{
		"folke/tokyonight.nvim",
		lazy = false, -- make sure we load this during startup if it is your main colorscheme
		priority = 1000, -- make sure to load this before all the other start plugins
		config = function()
			local tkn = require("tokyonight")
			tkn.setup({
				style = "storm",
				transparent = true,
				styles = {
					sidebars = "transparent",
				},
				on_highlights = function(hl, c)
					hl.CursorLineNr = {
						bg = "cyan",
						fg = "black",
					}
				end,
			})
			-- load the colorscheme here
			vim.cmd([[colorscheme tokyonight]])
		end,
	},
}
