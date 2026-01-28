vim.pack.add({
	{ src = "https://github.com/nvim-treesitter/nvim-treesitter" },
})

local configs = require("nvim-treesitter")
local ensure_installed = {
	"html",
	"c",
	"css",
	"scss",
	"lua",
	"luadoc",
	"vim",
	"vimdoc",
	"printf",
	"tsx",
	"typescript",
	"javascript",
	"dockerfile",
	"java",
	"yaml",
	"xml",
}
configs.setup({
	ensure_installed = ensure_installed,
	auto_install = true,
	sync_install = true,
	highlight = { enable = true },
	indent = { enable = true },
})
