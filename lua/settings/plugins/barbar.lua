return {
	"romgrk/barbar.nvim",
	config = function()
		require("barbar").setup({
			animation = true,
			auto_hide = false,
		})
	end,
}
