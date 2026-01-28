vim.pack.add({
	{ src = "https://github.com/folke/trouble.nvim" },
})

require("trouble").setup({
	modes = {
		diagnostics_buffer = {
			mode = "diagnostics",
			filter = { buf = 0 },
		},
		preview_float = {
			mode = "diagnostics",
			preview = {
				type = "float",
				relative = "editor",
				border = "rounded",
				title = "Preview",
				title_pos = "center",
				position = { 0, -2 },
				size = { width = 0.3, height = 0.3 },
				zindex = 200,
			},
		},
	},
})
