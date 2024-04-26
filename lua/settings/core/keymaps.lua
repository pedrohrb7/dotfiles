vim.g.mapleader = "\\"
vim.g.maplocalleader = "\\"

local keymap = vim.keymap -- for conciseness
local opts = { noremap = true, silent = true }
local term_opts = { silent = true }

keymap.set("i", "jk", "<ESC>", { desc = "Exit insert mode with jk" })
keymap.set("n", "<leader>nh", ":nohl<CR>", { desc = "Clear search highlights" })

-- increment/decrement numbers
keymap.set("n", "<leader>+", "<C-a>", { desc = "Increment number" }) -- increment
keymap.set("n", "<leader>-", "<C-x>", { desc = "Decrement number" }) -- decrement

-- custom buffer navigation
keymap.set("n", "<S-l>", "<cmd>bNext<CR>", { desc = "better way to navigate to next buffer" })
keymap.set("n", "<S-h>", "<cmd>bprevious<CR>", { desc = "better way to navigate to previous buffer" })
keymap.set("n", "<C-n>", "<cmd>tabnew<CR>", { desc = "better way to create new buffer" })
keymap.set("n", "<C-w>", "<cmd>tabclose<CR>", { desc = "Close current tab" }) -- close current tab
keymap.set("n", "<leader>tf", "<cmd>tabnew %<CR>", { desc = "Open current buffer in new tab" }) --  move current buffer to new tab

-- Navigate vim panes better
keymap.set("n", "<c-k>", ":wincmd k<CR>", { desc = "Go to panel above" })
keymap.set("n", "<c-j>", ":wincmd j<CR>", { desc = "Go to panel below" })
keymap.set("n", "<c-h>", ":wincmd h<CR>", { desc = "Go to the left panel" })
keymap.set("n", "<c-l>", ":wincmd l<CR>", { desc = "Go to the right panel" })

-- keymap.set("n", "<C-w>", "<cmd>:q")
keymap.set("n", "<C-s>", "<cmd>:update<CR>", { desc = "Update file changes" })
keymap.set("n", "<C-q>", "<cmd>:q<CR>", { desc = "Quit nvim" })

-- Visual Block --
-- Move text up and down
keymap.set("x", "<A-k>", ":move '<-2<CR>gv-gv", opts)
keymap.set("x", "<A-j>", ":move '>+1<CR>gv-gv", opts)
