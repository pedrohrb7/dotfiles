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
			local servers = {
				"jsonls",
				"lua_ls",
				"clangd",
				"tsserver",
				"kotlin_language_server",
				"terraformls",
				"dockerls",
				"tailwindcss",
				"cssls",
				"sqls",
				"terraformls",
				"hcl",
				"eslint",
			}

			require("mason-lspconfig").setup({
				ensure_installed = servers,
			})

			local capabilities = require("cmp_nvim_lsp").default_capabilities()

			require("mason-lspconfig").setup_handlers({
				-- ["tsserver"] = function()
				-- 	-- require("lspconfig").tsserver.setup()
				-- end,
				["lua_ls"] = function()
					require("lspconfig").lua_ls.setup()
				end,
				["eslint"] = function()
					require("lspconfig").eslint.setup()
				end,
			})

			require("typescript-tools").setup({
				on_attach = function(client, bufnr)
					client.server_capabilities.document_formatting = false
					client.server_capabilities.document_range_formatting = false
				end,
			})

			-- local lspconfig = require("lspconfig")
			-- lspconfig.eslint.setup({
			-- 	capabilities = capabilities,
			-- })
			-- lspconfig.ts_ls.setup({
			-- 	capabilities = capabilities,
			-- })
			-- lspconfig.solargraph.setup({
			-- 	capabilities = capabilities,
			-- })
			-- lspconfig.html.setup({
			-- 	capabilities = capabilities,
			-- })
			-- lspconfig.lua_ls.setup({
			-- 	capabilities = capabilities,
			-- })

			vim.keymap.set("n", "K", vim.lsp.buf.hover, {})
			vim.keymap.set("n", "gd", vim.lsp.buf.definition, { desc = "Go to definition" })
			vim.keymap.set("n", "gr", vim.lsp.buf.references, { desc = "Show references" })
			vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, { desc = "Open code actions" })
		end,
	},
}
