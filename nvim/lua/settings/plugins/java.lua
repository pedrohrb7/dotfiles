return {
	"nvim-java/nvim-java",
	depedencies = {
		"neovim/nvim-lspconfig",
	},
	config = function()
		require("java").setup()
		require("lspconfig").jdtls.setup({
			jdk = {
				-- install jdk using mason.nvim
				auto_install = true,
			},
		})
	end,
}
