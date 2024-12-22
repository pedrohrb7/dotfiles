vim.g.mapleader = '\\'
vim.g.maplocalleader = '\\'

local keymap = vim.keymap -- for conciseness
local opts = { noremap = true, silent = true }

keymap.set('i', 'jk', '<ESC>', opts, { desc = 'Exit insert mode with jk' })
keymap.set('n', '<leader>nh', ':nohl<CR>', opts, { desc = 'Clear search highlights' })

-- increment/decrement numbers
keymap.set('n', '<leader>+', '<C-a>', opts, { desc = 'Increment number' }) -- increment
keymap.set('n', '<leader>-', '<C-x>', opts, { desc = 'Decrement number' }) -- decrement

-- custom buffer navigation
keymap.set('n', '<S-l>', '<cmd>BufferNext<CR>', opts, { desc = 'better way to navigate to next buffer' })
keymap.set('n', '<S-h>', '<cmd>BufferPrevious<CR>', opts, { desc = 'better way to navigate to previous buffer' })
keymap.set('n', '<C-w>', '<cmd>BufferClose<CR>', opts, { desc = 'Close current tab' }) -- close current tab

-- Navigate vim panes better
keymap.set('n', '<c-k>', ':wincmd k<CR>', opts, { desc = 'Go to panel above' })
keymap.set('n', '<c-j>', ':wincmd j<CR>', opts, { desc = 'Go to panel below' })
keymap.set('n', '<c-h>', ':wincmd h<CR>', opts, { desc = 'Go to the left panel' })
keymap.set('n', '<c-l>', ':wincmd l<CR>', opts, { desc = 'Go to the right panel' })

-- keymap.set("n", "<C-w>", "<cmd>:q")
keymap.set('n', '<C-s>', '<cmd>:update<CR>', opts, { desc = 'Update file changes' })
keymap.set('n', '<C-q>', '<cmd>:q<CR>', opts, { desc = 'Quit nvim' })

-- Visual Block --
-- Move text up and down
keymap.set('n', '<A-j>', ':m .+1<CR>==', opts, { desc = 'move line up (normal mode)' }) -- move line up(n)
keymap.set('n', '<A-k>', ':m .-2<CR>==', opts, { desc = 'move line down(normal mode)' }) -- move line down(n)
keymap.set('v', '<A-k>', ":move '<-2<CR>gv-gv", opts, { desc = 'move text block up' })
keymap.set('v', '<A-j>', ":move '>+1<CR>gv-gv", opts, { desc = 'move text block down' })

-- Resize window using <ctrl> arrow keys
keymap.set('n', '<C-Up>', '<cmd>resize +2<cr>', opts, { desc = 'Increase Window Height' })
keymap.set('n', '<C-Down>', '<cmd>resize -2<cr>', opts, { desc = 'Decrease Window Height' })
keymap.set('n', '<C-Left>', '<cmd>vertical resize -2<cr>', opts, { desc = 'Decrease Window Width' })
keymap.set('n', '<C-Right>', '<cmd>vertical resize +2<cr>', opts, { desc = 'Increase Window Width' })

-- Stay in indent mode
vim.keymap.set('v', '<', '<gv', opts, { desc = 'Indent mode on back' })
vim.keymap.set('v', '>', '>gv', opts, { desc = 'Indent mode on indenting' })

-- Keep last yanked when pasting
vim.keymap.set('v', 'p', '"_dP', opts)

-- Autocommands
vim.api.nvim_create_augroup('custom_buffer', { clear = true })
-- highlight yanks
vim.api.nvim_create_autocmd('TextYankPost', {
  group = 'custom_buffer',
  pattern = '*',
  callback = function()
    vim.highlight.on_yank({ timeout = 200 })
  end,
})

-- ****************************
-- End Global keymaps
-- ****************************

-- *******************************
-- Plugins keymaps

--Neo-tree plugin
keymap.set('n', '<leader>ee', ':Neotree toggle<CR>', opts, { desc = 'Toggle file explorer' }) -- toggle file explorer
keymap.set('n', '<leader>bf', ':Neotree buffers reveal float<CR>', opts, { desc = 'Reveal buffers in modal' })
keymap.set('n', '--', ':Neotree reveal<CR>', opts, { desc = 'Reveal file under cursos' })

-- Telescope plugin
keymap.set('n', '<leader>ff', '<cmd>Telescop find_files<CR>', opts, { desc = 'Telescope Find file' })
keymap.set('n', '<leader>fg', '<cmd>Telescop live_grep<CR>', { desc = 'Telescope Search by word' })
keymap.set('n', '<leader>fb', '<cmd>Telescop buffers<CR>', { desc = 'Search in open buffers' })

-- Trouble plugin
keymap.set('n', '<leader>xx', '<cmd>Trouble diagnostics toggle<cr>', opts, { desc = 'Diagnostics (Trouble)' })
keymap.set(
  'n',
  '<leader>xX',
  '<cmd>Trouble diagnostics toggle filter.buf=0<cr>',
  opts,
  { desc = 'Buffer Diagnostics (Trouble)' }
)

-- Theme manager plugin
keymap.set('n', '<leader>tt', '<cmd>Themery<CR>', opts, { desc = 'Themery choose theme' })

-- GitSigns Plugin
keymap.set('n', ']h', ':Gitsigns next_hunk<CR>', opts, { desc = 'GitSigns Next Hunk' })
keymap.set('n', '[h', ':Gitsigns prev_hunk<CR>', opts, { desc = 'GitSigns Prev Hunk' })

keymap.set('n', '<leader>hs', ':Gitsigns stage_hunk<CR>', opts, { desc = 'GitSigns Stage hunk in NORMAL mode' })
keymap.set('v', '<leader>hs', ':Gitsigns stage_hunk<CR>', opts, { desc = 'GitSigns Stage hunk in VISUAL mode' })

keymap.set('n', '<leader>hr', ':Gitsigns reset_hunk<CR>', opts, { desc = 'GitSigns reset hunk in NORMAL mode' })
keymap.set('v', '<leader>hr', ':Gitsigns reset_hunk<CR>', opts, { desc = 'GitSigns reset hunk in VISUAL mode' })

keymap.set('n', '<leader>hS', '<cmd>Gitsigns stage_buffer<CR>', opts, { desc = 'GitSigns Stage Buffer' })
keymap.set('n', '<leader>hR', '<cmd>Gitsigns reset_buffer<CR>', opts, { desc = 'GitSigns RESET Buffer' })

keymap.set('n', '<leader>hd', '<cmd>lua require"gitsigns".diffthis("~")<CR>', opts, { desc = 'GitSigns VDiffThis ' })
keymap.set('n', '<leader>hu', '<cmd>Gitsigns undo_stage_hunk<CR>', opts, { desc = 'GitSigns Undo Stage Hunk' })
keymap.set(
  'n',
  '<leader>hb',
  '<cmd>lua require"gitsigns".blame_line{full=true}<CR>',
  opts,
  { desc = 'GitSigns Blame Full' }
)
keymap.set('n', '<leader>hp', '<cmd>Gitsigns preview_hunk<CR>', opts, { desc = 'GitSigns Show Hunk Preview' })
keymap.set('n', '<leader>td', '<cmd>Gitsigns toggle_deleted<CR>', opts, { desc = 'GitSigns Toggle Deleted' })
-- End GitSigns Plugin

-- LazyGit Plugin
keymap.set('n', '<leader>lg', ':LazyGitCurrentFile<CR>', opts, { desc = 'LazyGit Current File' })

-- LazyDocker Plugin
keymap.set('n', '<leader>ld', ':Lazydocker<CR>', opts, { desc = 'LazyGit Current File' })

-- Conform Plugin (formatting.lua)
keymap.set('n', '<leader>mp', function()
  local conform = require('conform')
  conform.format({
    lsp_fallback = true,
    async = false,
    timeout_ms = 500,
  })
end, { desc = 'Conform Format file or range' })

-- ToggleTerm Plugin
keymap.set('n', '<C-t>', ':ToggleTerm<CR>', opts, { desc = 'ToggleTerm on float mode' })
keymap.set('v', '<S-t>', ':ToggleTermSendVisualSelection<CR>', opts, { desc = 'ToggleTerm send Visual Selection' })

-- Noice Plugin
-- This will help when a lot of notifications appears
keymap.set('n', '<leader>nd', ':NoiceDismiss<CR>', opts, { desc = 'Noice Dismiss notification' })

-- LSP Signature Help Plugin
keymap.set('n', '<leader>k', function()
  vim.lsp.buf.signature_help()
end, opts, { desc = 'toggle signature' })
