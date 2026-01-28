vim.cmd("let g:netrw_liststyle = 3")

local keymap = vim.keymap
local opts = { noremap = true, silent = true }

keymap.set("i", "jl", "<ESC>", opts)
keymap.set("n", "<leader>nh", ":nohl<CR>", opts)

-- increment/decrement numbers
keymap.set("n", "<leader>+", "<C-a>", opts) -- increment
keymap.set("n", "<leader>-", "<C-x>", opts) -- decrement

keymap.set("n", "<C-s>", "<cmd>:update<CR>", opts) -- opts) -- "Update file changes" })
keymap.set("n", "<C-q>", "<cmd>:q<CR>", opts) -- "Quit nvim" })

-- Visual Block --
-- Move text up and down
keymap.set("n", "<A-j>", ":m .+1<CR>==", opts) -- "move line up (normal mode)" }) -- move line up(n)
keymap.set("n", "<A-k>", ":m .-2<CR>==", opts) -- "move line down(normal mode)" }) -- move line down(n)
keymap.set("v", "<A-k>", ":move '<-2<CR>gv-gv", opts) -- "move text block up" })
keymap.set("v", "<A-j>", ":move '>+1<CR>gv-gv", opts) -- "move text block down" })

-- Navigate vim panes better
keymap.set("n", "<c-k>", ":wincmd k<CR>", opts) -- "Go to panel above" })
keymap.set("n", "<c-j>", ":wincmd j<CR>", opts) -- "Go to panel below" })
keymap.set("n", "<c-h>", ":wincmd h<CR>", opts) -- "Go to the left panel" })
keymap.set("n", "<c-l>", ":wincmd l<CR>", opts) -- "Go to the right panel" })

--  buffer navigation
keymap.set("n", "<S-l>", ":bnext<CR>", opts) --, { desc = "better way to navigate to next buffer" })
keymap.set("n", "<S-h>", ":bprev<CR>", opts) --, { desc = "better way to navigate to previous buffer" })

-- Easily split windows
vim.keymap.set("n", "<leader>wv", ":vsplit<cr>", { desc = "[W]indow Split [V]ertical" })
vim.keymap.set("n", "<leader>wh", ":split<cr>", { desc = "[W]indow Split [H]orizontal" })

-- Resize window using <ctrl> arrow keys
keymap.set("n", "<C-Up>", "<cmd>resize +2<cr>", opts)
keymap.set("n", "<C-Down>", "<cmd>resize -2<cr>", opts)
keymap.set("n", "<C-Left>", "<cmd>vertical resize -2<cr>", opts)
keymap.set("n", "<C-Right>", "<cmd>vertical resize +2<cr>", opts)

-- Stay in indent mode
keymap.set("v", "<", "<gv", opts) -- "Indent mode on back" })
keymap.set("v", ">", ">gv", opts) -- "Indent mode on indenting" })

-- Keep last yanked when pasting
keymap.set("v", "p", '"_dP', opts)

-- insert new line
keymap.set("n", "<leader>o", "o<ESC>", opts)
keymap.set("n", "<leader>O", "O<ESC>", opts)

-- #######################################
-- Plugins keymaps
-- #######################################

--Neo-tree plugin
keymap.set("n", "<leader>ne", ":Neotree toggle<CR>", opts) -- "Toggle file explorer" }) -- toggle file explorer
keymap.set("n", "<C-t>", ":Neotree toggle<CR>", opts) -- "Alternative map to toggle file explorer" }) -- toggle file explorer
keymap.set("n", "<leader>nb", ":Neotree buffers reveal float<CR>", opts) -- "Reveal buffers in modal" })
keymap.set("n", "--", ":Neotree reveal<CR>", opts) -- "Reveal file under cursos" })

-- Telescope plugin
keymap.set("n", "<leader>tf", "<cmd>Telescop find_files<CR>", opts) -- "Telescope Find file" })
keymap.set("n", "<leader>tg", "<cmd>Telescop live_grep<CR>", opts) -- "Telescope Search by word" })
keymap.set("n", "<leader>tb", "<cmd>Telescop buffers<CR>", opts) -- "Search in open buffers" })

-- Trouble plugin
keymap.set("n", "<leader>xx", "<cmd>Trouble diagnostics toggle<cr>", opts) -- "Diagnostics (Trouble)" })
keymap.set("n", "<leader>xX", "<cmd>Trouble diagnostics toggle filter.buf=0<cr>", opts) -- "Buffer Diagnostics (Trouble)" }

-- GitSigns Plugin
keymap.set("n", "]h", ":Gitsigns next_hunk<CR>", opts) -- "GitSigns Next Hunk" })
keymap.set("n", "[h", ":Gitsigns prev_hunk<CR>", opts) -- "GitSigns Prev Hunk" })

keymap.set("n", "<leader>hs", ":Gitsigns stage_hunk<CR>", opts) -- "GitSigns Stage hunk in NORMAL mode" })
keymap.set("v", "<leader>hs", ":Gitsigns stage_hunk<CR>", opts) -- "GitSigns Stage hunk in VISUAL mode" })

keymap.set("n", "<leader>hr", ":Gitsigns reset_hunk<CR>", opts) -- "GitSigns reset hunk in NORMAL mode" })
keymap.set("v", "<leader>hr", ":Gitsigns reset_hunk<CR>", opts) -- "GitSigns reset hunk in VISUAL mode" })

keymap.set("n", "<leader>hS", "<cmd>Gitsigns stage_buffer<CR>", opts) -- "GitSigns Stage Buffer" })
keymap.set("n", "<leader>hR", "<cmd>Gitsigns reset_buffer<CR>", opts) -- "GitSigns RESET Buffer" })

keymap.set("n", "<leader>hd", '<cmd>lua require"gitsigns".diffthis("~")<CR>', opts) -- "GitSigns VDiffThis " })
keymap.set("n", "<leader>hu", "<cmd>Gitsigns undo_stage_hunk<CR>", opts) -- "GitSigns Undo Stage Hunk" })
keymap.set("n", "<leader>hb", '<cmd>lua require"gitsigns".blame_line{full=true}<CR>', opts) -- "GitSigns Blame Full" })
keymap.set("n", "<leader>hp", "<cmd>Gitsigns preview_hunk<CR>", opts) -- "GitSigns Show Hunk Preview" })
keymap.set("n", "<leader>td", "<cmd>Gitsigns toggle_deleted<CR>", opts) -- "GitSigns Toggle Deleted" })
-- End GitSigns Plugin

-- Format with conform
keymap.set("n", "<leader>mp", function()
	local conform = require("conform")
	conform.format({
		lsp_fallback = true,
		async = false,
		timeout_ms = 500,
	})
end, opts) -- "Conform Format file or range" })
