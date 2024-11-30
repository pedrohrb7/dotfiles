vim.g.mapleader = "\\"
vim.g.maplocalleader = "\\"

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

-- Plugins keymaps

--Neo-tree plugin
keymap.set("n", "-", function()
  local reveal_file = vim.fn.expand("%:p")
  if reveal_file == "" then
    reveal_file = vim.fn.getcwd()
  else
    local f = io.open(reveal_file, "r")
    if f then
      f.close(f)
    else
      reveal_file = vim.fn.getcwd()
    end
  end
  require("neo-tree.command").execute({
    reveal_file = reveal_file, -- path to file or folder to reveal
    reveal_force_cwd = true, -- change cwd without asking if needed
  })
end, { desc = "Open neo-tree at current file or working directory" })
keymap.set("n", "<leader>ee", "<cmd>Neotree toggle<CR>", { desc = "Toggle file explorer" }) -- toggle file explorer
keymap.set("n", "<leader>bf", ":Neotree buffers reveal float<CR>", { desc = "Reveal buffers in modal" })
keymap.set("n", "--", ":Neotree reveal<CR>", { noremap = true, silent = true }, { desc = "Reveal file under cursos" })
-- End Neo-tree plugin

-- Telescope plugin
keymap.set("n", "<leader>ff", "<cmd>Telescop find_files<CR>", opts, { desc = "Telescope Find file" })
keymap.set("n", "<leader>fg", "<cmd>Telescop live_grep<CR>", { desc = "Telescope Search by word" })
keymap.set("n", "<leader>fb", "<cmd>Telescop buffers<CR>", { desc = "Search in open buffers" })
-- keymap.set("n", "<leader>fh", builtin.help_tags, {})
-- End Telescope plugin

-- Trouble plugin
keymap.set("n", "<leader>xx", "<cmd>Trouble diagnostics toggle<cr>", opts, { desc = "Diagnostics (Trouble)" })
keymap.set(
  "n",
  "<leader>xX",
  "<cmd>Trouble diagnostics toggle filter.buf=0<cr>",
  opts,
  { desc = "Buffer Diagnostics (Trouble)" }
)
keymap.set("n", "<leader>cs", "<cmd>Trouble symbols toggle focus=true<cr>", opts, { desc = "Symbols (Trouble)" })
keymap.set(
  "n",
  "<leader>cl",
  "<cmd>Trouble lsp toggle focus=false win.position=right<cr>",
  opts,
  { desc = "LSP Definitions / references / ... (Trouble)" }
)
keymap.set("n", "<leader>xL", "<cmd>Trouble loclist toggle<cr>", opts, { desc = "Location List (Trouble)" })
keymap.set("n", "<leader>xQ", "<cmd>Trouble qflist toggle<cr>", opts, { desc = "Quickfix List (Trouble)" })
-- End Trouble plugin

-- Theme manager plugin
keymap.set("n", "<leader>tt", "<cmd>Themery<CR>", opts, { desc = "Themery choose theme" })

-- GitSigns Plugin
keymap.set("n", "]h", ":Gitsigns next_hunk<CR>", opts, { desc = "GitSigns Next Hunk" })
keymap.set("n", "[h", ":Gitsigns prev_hunk<CR>", opts, { desc = "GitSigns Prev Hunk" })

-- Typescript Tools Plugin
keymap.set("n", "gd", "<cmd>TSToolsGoToSourceDefinition<CR>", opts, { desc = "TypescriptTools GoTo Source Definition" })
keymap.set("n", "gr", "<cmd>TSToolsFileReferences<CR>", opts, { desc = "TypescriptTools GoTo References" })
keymap.set("n", "gf", "<cmd>TSToolsFixAll<CR>", opts, { desc = "TypescriptTools FixAll" })

-- Substitute Plugin
--
--

-- Conform Plugin (formatting.lua)
keymap.set("n", "<leader>mp", function()
  local conform = require("conform")
  conform.format({
    lsp_fallback = true,
    async = false,
    timeout_ms = 500,
  })
end, { desc = "Conform Format file or range" })
