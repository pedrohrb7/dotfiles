return {
	{
		"williamboman/mason.nvim",
		lazy = false,
		config = function()
			require("mason").setup({
				ui = {
					border = "rounded",
					icons = {
						package_installed = "✓",
						package_pending = "➜",
						package_uninstalled = "✗",
					},
				},
			})
		end,
	},
	{
		"williamboman/mason-lspconfig.nvim",
		lazy = false,
		opts = {
			auto_install = true,
		},
	},
	{
		"neovim/nvim-lspconfig",
		lazy = false,
		event = { "BufReadPre", "BufNewFile" },
		dependencies = {
			{ "williamboman/mason.nvim", config = true },
			"williamboman/mason-lspconfig.nvim",
			{ "j-hui/fidget.nvim", opts = {} },
			"folke/neodev.nvim",
			{ "b0o/schemastore.nvim" },
			{ "hrsh7th/cmp-nvim-lsp" },
			{ "HiPhish/rainbow-delimiters.nvim" },
			{ "b0o/schemastore.nvim" },
			{ "ray-x/navigator.lua" },
			{ "ray-x/guihua.lua", run = "cd lua/fzy && make" },
			"ray-x/guihua.lua",
			"nvim-treesitter/nvim-treesitter",
			"nvim-lua/plenary.nvim",
			"stevearc/dressing.nvim", -- optional for vim.ui.select
			"pmizio/typescript-tools.nvim",
			"jay-babu/mason-null-ls.nvim",
		},
		config = function()
			local mason_null_ls = require("mason-null-ls")
			mason_null_ls.setup({
				ensure_installed = {
					"prettier", -- prettier formatter
					"stylua", -- lua formatter
					"eslint", -- js linter
					"terraform_fmt", -- terraform formatter
					"terraform_validate", -- terraform linter
					"shellcheck", -- shell linter
					"buf", -- buf formatter
					"yamlfmt", -- yaml formatter
					"spell", -- spell checker
				},
			})

			local capabilities = require("cmp_nvim_lsp").default_capabilities()

			local lspconfig = require("lspconfig")
			lspconfig.tsserver.setup({
				capabilities = capabilities,
			})
			lspconfig.solargraph.setup({
				capabilities = capabilities,
			})
			lspconfig.html.setup({
				capabilities = capabilities,
			})
			lspconfig.lua_ls.setup({
				capabilities = capabilities,
			})

			vim.keymap.set("n", "K", vim.lsp.buf.hover, {})
			vim.keymap.set("n", "<leader>gd", vim.lsp.buf.definition, { desc = "Got to definition" })
			vim.keymap.set("n", "<leader>gr", vim.lsp.buf.references, { desc = "Show references" })
			vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, { desc = "Open code actions" })
		end,
	},
}
