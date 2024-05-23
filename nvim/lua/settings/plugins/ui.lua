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
				-- transparent = true,
				-- styles = {
				-- 	sidebars = "transparent",
				-- },
				on_highlights = function(hl, c)
					hl.CursorLineNr = {
						bg = "cyan",
						fg = "black",
					}
				end,
			})
			-- vim.cmd([[colorscheme tokyonight]])
		end,
	},
	{
		"scottmckendry/cyberdream.nvim",
		lazy = false,
		priority = 1000,
		config = function()
			require("cyberdream").setup({
				-- Recommended - see "Configuring" below for more config options
				transparent = false,
				italic_comments = true,
				hide_fillchars = true,
				borderless_telescope = true,
				terminal_colors = true,
			})
			-- vim.cmd([[colorscheme cyberdream]])
		end,
	},
	{
		"oxfist/night-owl.nvim",
		lazy = false, -- make sure we load this during startup if it is your main colorscheme
		priority = 1000, -- make sure to load this before all the other start plugins
		config = function()
			-- load the colorscheme here
			require("night-owl").setup()
			-- vim.cmd([[colorscheme night-owl]])
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
					comments = { italic = false, bold = true },
					functions = { italic = true },
					variables = { italic = false },
				},
			})
		end,
	},
}
