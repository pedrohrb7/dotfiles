return {
	"nvimtools/none-ls.nvim",
	dependencies = {
		"nvimtools/none-ls-extras.nvim",
		"gbprod/none-ls-php.nvim",
	},
	config = function()
		local null_ls = require("null-ls")
		local null_ls_utils = require("null-ls.utils")

		null_ls.setup({
			root_dir = null_ls_utils.root_pattern(".null-ls-root", "Makefile", ".git", "package.json"),
			sources = {
				-- Formatters
				null_ls.builtins.formatting.prettierd,
				null_ls.builtins.formatting.google_java_format,
				null_ls.builtins.formatting.stylelint,

				-- Diagnostics
				null_ls.builtins.diagnostics.stylelint,
				null_ls.builtins.diagnostics.editorconfig_checker,
				-- null_ls.builtins.diagnostics.eslint,
				-- null_ls.builtins.diagnostics.eslint.with({
				-- 	condition = function(utils)
				-- 		-- Verifica se um arquivo de configuração do eslint existe na raiz do projeto
				-- 		return utils.root_has_file({
				-- 			".eslint.json",
				-- 			".eslintrc.js",
				-- 			".eslintrc.cjs",
				-- 			".eslintrc",
				-- 		})
				-- 	end,
				-- 	-- Certifica-se de que o eslint usa o arquivo de configuração na raiz do projeto
				-- 	extra_args = function(params)
				-- 		-- Passa o caminho do arquivo de configuração como argumento
				-- 		return { "--config", params.root .. "/.eslintrc.js" }
				-- 	end,
				-- }),

				-- Code Actions
				-- require("none-ls.code_actions.eslint").with({
				-- 	condition = function(utils)
				-- 		return utils.root_has_file({
				-- 			".eslint.json",
				-- 			".eslintrc.js",
				-- 			".eslintrc.cjs",
				-- 			".eslintrc",
				-- 		})
				-- 	end,
				-- }),
			},
		})

		vim.keymap.set("n", "<leader>fc", vim.lsp.buf.format, { desc = "format document or selected block" })
	end,
}
