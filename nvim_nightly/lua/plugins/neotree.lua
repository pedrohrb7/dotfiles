vim.pack.add({
	{ src = "https://github.com/nvim-neo-tree/neo-tree.nvim" },
	{ src = "https://github.com/nvim-lua/plenary.nvim" },
	{ src = "https://github.com/nvim-tree/nvim-web-devicons" },
	{ src = "https://github.com/MunifTanjim/nui.nvim" },
})

local neoTree = require("neo-tree")
neoTree.setup({
	close_if_last_window = true,
	window = {
		position = "right",
		mappings = {
			["h"] = "close_node",
			["l"] = "toggle_node",
			["A"] = "add_directory",
			["Y"] = function(state)
				local node = state.tree:get_node()
				local filepath = node:get_id()
				vim.fn.setreg('"', filepath)
				vim.notify("Copied: " .. filepath)
			end,
		},
	},
	filesystem = {
		filtered_items = {
			hide_dotfiles = false,
			hide_gitignored = false,
		},
		follow_current_file = {
			enabled = true,
		},
	},
	buffers = {
		follow_current_file = {
			enabled = true,
		},
	},
})
