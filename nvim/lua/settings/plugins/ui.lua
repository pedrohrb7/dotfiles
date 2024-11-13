return {
	-- the colorscheme should be available when starting Neovim
	{
		"folke/tokyonight.nvim",
		lazy = false, -- make sure we load this during startup if it is your main colorscheme
		priority = 1000, -- make sure to load this before all the other start plugins
		config = function()
			local tkn = require("tokyonight")
			tkn.setup({
				style = "night",
				transparent = true,
				styles = {
					sidebars = "transparent",
					comments = { italic = true, bold = true },
					functions = { italic = true },
					variables = { italic = true },
				},
				on_highlights = function(hl)
					hl.CursorLineNr = {
						bg = "cyan",
						fg = "black",
					}
				end,
			})
			vim.cmd([[colorscheme tokyonight]])
		end,
	},

	{
		"maxmx03/solarized.nvim",
		lazy = false,
		priority = 1000,
		config = function()
			require("solarized").setup({
				transparent = false, -- enable transparent background
				styles = {
					comments = { italic = true, bold = true },
					functions = { italic = true },
					variables = { italic = true },
				},
			})
		end,
	},
}
