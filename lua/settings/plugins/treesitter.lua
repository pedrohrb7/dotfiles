return {
	"nvim-treesitter/nvim-treesitter",
	build = ":TSUpdate",

	config = function()
		local configs = require("nvim-treesitter.configs")
		configs.setup({
			-- ensure_installed = { "angular", "jsonc", "kotlin", "php", "prisma", "pug", "vue", "scss", "xml", "c", "lua", "vim", "vimdoc", "css", "tsx", "typescript", "dockerfile", "yaml", "javascript", "html" },
			auto_install = true,
			sync_install = false,
			highlight = { enable = true },
			indent = { enable = true },
		})
	end,
}
