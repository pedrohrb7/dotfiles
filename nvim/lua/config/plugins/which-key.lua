return {
	"folke/which-key.nvim",
	event = "VeryLazy",
	opts = {
		---@type false | "classic" | "modern" | "helix"
		preset = "modern",
	},
	keys = {
		{
			"<leader>",
			function()
        local wk = require("which-key") 

				wk.show({ global = true })
			end,
			desc = "Buffer Local Keymaps (which-key)",
		},
	},
}
