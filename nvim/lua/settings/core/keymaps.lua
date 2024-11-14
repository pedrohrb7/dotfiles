vim.g.mapleader = "\\"
-- vim.g.maplocalleader = "\\"

local keymap = vim.keymap -- for conciseness
local opts = { noremap = true, silent = true }
-- local term_opts = { silent = true }

keymap.set("i", "jk", "<ESC>", opts, { desc = "Exit insert mode with jk" })
keymap.set("n", "<leader>nh", ":nohl<CR>", opts, { desc = "Clear search highlights" })

-- increment/decrement numbers
keymap.set("n", "<leader>+", "<C-a>", opts, { desc = "Increment number" }) -- increment
keymap.set("n", "<leader>-", "<C-x>", opts, { desc = "Decrement number" }) -- decrement

-- custom buffer navigation
keymap.set("n", "<S-l>", "<cmd>bnext<CR>", opts, { desc = "better way to navigate to next buffer" })
keymap.set("n", "<S-h>", "<cmd>bprevious<CR>", opts, { desc = "better way to navigate to previous buffer" })
keymap.set("n", "<C-n>", "<cmd>tabnew<CR>", opts, { desc = "better way to create new buffer" })
keymap.set("n", "<C-w>", "<cmd>BufferClose<CR>", opts, { desc = "Close current tab" }) -- close current tab

-- Navigate vim panes better
keymap.set("n", "<c-k>", ":wincmd k<CR>", opts, { desc = "Go to panel above" })
keymap.set("n", "<c-j>", ":wincmd j<CR>", opts, { desc = "Go to panel below" })
keymap.set("n", "<c-h>", ":wincmd h<CR>", opts, { desc = "Go to the left panel" })
keymap.set("n", "<c-l>", ":wincmd l<CR>", opts, { desc = "Go to the right panel" })

-- keymap.set("n", "<C-w>", "<cmd>:q")
keymap.set("n", "<C-s>", "<cmd>:update<CR>", opts, { desc = "Update file changes" })
keymap.set("n", "<C-q>", "<cmd>:q<CR>", opts, { desc = "Quit nvim" })

-- Visual Block --
-- Move text up and down
keymap.set("n", "<A-j>", ":m .+1<CR>==", opts, { desc = "move line up (normal mode)" }) -- move line up(n)
keymap.set("n", "<A-k>", ":m .-2<CR>==", opts, { desc = "move line down(normal mode)" }) -- move line down(n)
keymap.set("v", "<A-k>", ":move '<-2<CR>gv-gv", opts, { desc = "move text block up" })
keymap.set("v", "<A-j>", ":move '>+1<CR>gv-gv", opts, { desc = "move text block down" })

-- Resize window using <ctrl> arrow keys
keymap.set("n", "<C-Up>", "<cmd>resize +2<cr>", opts, { desc = "Increase Window Height" })
keymap.set("n", "<C-Down>", "<cmd>resize -2<cr>", opts, { desc = "Decrease Window Height" })
keymap.set("n", "<C-Left>", "<cmd>vertical resize -2<cr>", opts, { desc = "Decrease Window Width" })
keymap.set("n", "<C-Right>", "<cmd>vertical resize +2<cr>", opts, { desc = "Increase Window Width" })
