return {
	"nvimtools/none-ls.nvim",
	dependencies = {
		"nvimtools/none-ls-extras.nvim",
		"gbprod/none-ls-php.nvim",
	},
	config = function()
		local null_ls = require("null-ls")
		local formatting = null_ls.builtins.formatting
		-- local diagnostics = null_ls.builtins.diagnostics
		local null_ls_utils = require("null-ls.utils")
		-- local code_actions = null_ls.builtins.code_actions

		null_ls.setup({
			root_dir = null_ls_utils.root_pattern(".null-ls-root", "Makefile", ".git", "package.json"),
			sources = {
				formatting.stylua,
				formatting.prettier,
				require("none-ls-php.diagnostics.php"),
				require("none-ls.code_actions.eslint").with({
					condition = function(utils)
						return utils.root_has_file({ ".eslint.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc" }) -- only enable if root has .eslintrc file
					end,
				}),
				require("none-ls.diagnostics.eslint").with({
					condition = function(utils)
						return utils.root_has_file({ ".eslint.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc" }) -- only enable if root has .eslintrc file
					end,
				}),
				-- diagnostics.eslint_d,
				-- diagnostics.eslint_d.with({ -- js/ts linter
				-- 	condition = function(utils)
				-- 		return utils.root_has_file({ ".eslint.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc" }) -- only enable if root has .eslintrc file
				-- 	end,
				-- }),
			},
		})

		vim.keymap.set("n", "<leader>fc", vim.lsp.buf.format, { desc = "format document or selected block" })
	end,
}
