return {
	"nvim-lualine/lualine.nvim",
	dependencies = { "nvim-tree/nvim-web-devicons" },

	config = function()
		local luaLine = require("lualine")
		luaLine.setup({
			options = {
				icons_enabled = true,
				theme = "ayu_dark",
				disabled_filetypes = {
					statusline = { "neo-tree", "alpha" },
				},
			},
		})
	end,
}
