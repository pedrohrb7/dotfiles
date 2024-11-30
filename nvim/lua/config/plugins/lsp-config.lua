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
			{ "hrsh7th/cmp-nvim-lsp" },
			"jay-babu/mason-null-ls.nvim",
			"williamboman/mason-lspconfig.nvim",
			"nvim-treesitter/nvim-treesitter",
			"pmizio/typescript-tools.nvim",
			"nvim-lua/plenary.nvim",
		},
		config = function()
			local mson = require("mason")
			local tstools = require("typescript-tools")
			local capabilities = require("cmp_nvim_lsp").default_capabilities()
			local lspconfig = require("lspconfig")
			local mson_lspconfig = require("mason-lspconfig")

			mson.setup({
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
				"ts_ls",
				"kotlin_language_server",
				"terraformls",
				"dockerls",
				"tailwindcss",
				"cssls",
				"sqls",
				"terraformls",
				"eslint",
			}

			mson_lspconfig.setup({
				ensure_installed = servers,
			})

			mson_lspconfig.setup_handlers({
				-- ["tsserver"] = function()
				-- 	-- require("lspconfig").tsserver.setup()
				-- end,
				-- ["lua_ls"] = function()
				-- 	lspconfig.lua_ls.setup()
				-- end,
				lspconfig.lua_ls.setup({
					capabilities = capabilities,
					-- on_attach = on_attach,
					settings = {
						Lua = {
							format = {
								enable = true,
								-- Put format options here
								-- NOTE: the value should be STRING!!
								defaultConfig = {
									indent_style = "space",
									indent_size = "2",
								},
							},
						},
					},
				}),
				lspconfig.eslint.setup({
					-- capabilities = capibilities,
					flags = { debounce_text_changes = 500 },
					root_dir = lspconfig.util.root_pattern("package.json"),
					filetypes = {
						"typescript",
						"typescriptreact",
						"javascriptreact",
					},
					single_file_suppoter = true,
				}),
			})

			tstools.setup({
				settings = {
					jsx_close_tag = {
						enable = true,
						filetypes = { "javascriptreact", "typescriptreact" },
					},
				},
				on_attach = function(client)
					client.server_capabilities.document_formatting = false
					client.server_capabilities.document_range_formatting = false
				end,
			})
		end,
	},
}
