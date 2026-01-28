vim.pack.add({
	{ src = "https://github.com/nvim-telescope/telescope.nvim" },
	{ src = "https://github.com/nvim-lua/plenary.nvim" },
	{ src = "https://github.com/nvim-telescope/telescope-fzf-native.nvim" },
	{ src = "https://github.com/nvim-telescope/telescope-ui-select.nvim" },
	{ src = "https://github.com/nvim-telescope/telescope-media-files.nvim" },
	{ src = "https://github.com/nvim-tree/nvim-web-devicons" },
	{ src = "https://github.com/folke/todo-comments.nvim" },
})

local telescope = require("telescope")
local actions = require("telescope.actions")
local transform_mod = require("telescope.actions.mt").transform_mod

local trouble = require("trouble")
local trouble_telescope = require("trouble.sources.telescope")

-- or create your custom action
local custom_actions = transform_mod({
	open_trouble_qflist = function()
		trouble.toggle("quickfix")
	end,
})

telescope.setup({
	defaults = {
		path_display = { "smart" },
		file_ignore_patterns = {
			"node_modules",
			".next",
			"dist",
			"bundle",
			".git",
			".yarn",
		},
		mappings = {
			i = {
				["<C-k>"] = actions.move_selection_previous, -- move to prev result
				["<C-j>"] = actions.move_selection_next, -- move to next result
				["<C-q>"] = actions.send_selected_to_qflist + custom_actions.open_trouble_qflist,
				["<C-t>"] = trouble_telescope.smart_open_with_trouble,
			},
		},
	},
	pickers = {
		colorscheme = {
			enable_preview = true,
		},
		find_files = {
			theme = "ivy",
			hidden = true,
		},
	},
	extensions = {
		media_files = {
			-- filetypes whitelist
			-- defaults to {"png", "jpg", "mp4", "webm", "pdf"}
			filetypes = { "png", "webp", "jpg", "jpeg", "pdf" },
			-- find command (defaults to `fd`)
			find_cmd = "fd",
		},
	},
})

-- telescope.load_extension("fzf")
telescope.load_extension("ui-select")
telescope.load_extension("media_files")
