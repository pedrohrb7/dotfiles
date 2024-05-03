return {
	"brenoprata10/nvim-highlight-colors",
	config = function()
		local highColors = require("nvim-highlight-colors")

		highColors.setup({
			render = "background",
			enable_named_colors = true,
			enable_tailwind = true,
		})
	end,
}
