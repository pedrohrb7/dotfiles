return {
	{
		"lewis6991/gitsigns.nvim",
		config = function()
			local setmap = vim.keymap
			require("gitsigns").setup({
				signs = {
					add = { text = "┃" },
					change = { text = "┃" },
					delete = { text = "_" },
					topdelete = { text = "‾" },
					changedelete = { text = "~" },
					untracked = { text = "┆" },
				},
				watch_gitdir = {
					follow_files = true,
				},
				signcolumn = true, -- Toggle with `:Gitsigns toggle_signs`
				numhl = true, -- Toggle with `:Gitsigns toggle_numhl`
				linehl = false, -- Toggle with `:Gitsigns toggle_linehl`
				word_diff = false, -- Toggle with `:Gitsigns toggle_word_diff`
				current_line_blame = true,
			})

			-- Navigation
			setmap.set("n", "]h", ":Gitsigns next_hunk<CR>", { desc = "Next Hunk" })
			setmap.set("n", "[h", ":Gitsigns prev_hunk<CR>", { desc = "Prev Hunk" })
		end,
	},
	{
		"tpope/vim-fugitive",
	},
}
