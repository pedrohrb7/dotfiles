return { -- Useful plugin to show you pending keybinds.
  'folke/which-key.nvim',
  event = 'VimEnter', -- Sets the loading event to 'VimEnter'
  opts = {
    -- delay between pressing a key and opening which-key (milliseconds)
    -- this setting is independent of vim.o.timeoutlen
    delay = 0,
    icons = {
      -- set icon mappings to true if you have a Nerd Font
      mappings = vim.g.have_nerd_font,
      -- If you are using a Nerd Font: set icons.keys to an empty table which will use the
      -- default which-key.nvim defined Nerd Font icons, otherwise define a string table
      keys = vim.g.have_nerd_font and {} or {
        Up = ' ',
        Down = ' ',
        Left = ' ',
        Right = ' ',
        C = '󰘴 ',
        M = '󰘵 ',
        D = '󰘳 ',
        S = '󰘶 ',
        CR = '󰌑 ',
        Esc = '󱊷 ',
        ScrollWheelDown = '󱕐 ',
        ScrollWheelUp = '󱕑 ',
        NL = '󰌑 ',
        BS = '󰁮',
        Space = '󱁐 ',
        Tab = '󰌒 ',
        F1 = '󱊫',
        F2 = '󱊬',
        F3 = '󱊭',
        F4 = '󱊮',
        F5 = '󱊯',
        F6 = '󱊰',
        F7 = '󱊱',
        F8 = '󱊲',
        F9 = '󱊳',
        F10 = '󱊴',
        F11 = '󱊵',
        F12 = '󱊶',
      },
    },

    -- Document existing key chains
    spec = {
      { '<leader>s', group = '[S]earch' },
      { '<leader>t', group = '[T]oggle' },
      { '<leader>h', group = 'Git [H]unk', mode = { 'n', 'v' } },
    },
  },
}

--
-- return {
--   'folke/which-key.nvim',
--   event = 'VeryLazy',
--   lazy = true,
--   opts = {
--     ---@type false | "classic" | "modern" | "helix"
--     preset = 'helix',
--     icons = {
--       breadcrumb = '»', -- symbol used in the command line area that shows your active key combo
--       separator = '➜', -- symbol used between a key and it's label
--       group = '+', -- symbol prepended to a group
--       ellipsis = '…',
--       -- set to false to disable all mapping icons,
--       -- both those explicitly added in a mapping
--       -- and those from rules
--       mappings = true,
--       --- See `lua/which-key/icons.lua` for more details
--       --- Set to `false` to disable keymap icons from rules
--       ---@type wk.IconRule[]|false
--       rules = {},
--       -- use the highlights from mini.icons
--       -- When `false`, it will use `WhichKeyIcon` instead
--       colors = true,
--       -- used by key format
--       keys = ,
--     },
--     show_help = true, -- show a help message in the command line for using WhichKey
--     show_keys = true, -- show the currently pressed key and its label as a message in the command line
--   },
--   confi = function()
--     local wk = require('which-key')
--
--     wk.setup(opts)
--     wk.registers('config.core.keymaps', {
--       mode = 'n', -- NORMAL mode
--       prefix = '<leader>',
--       buffer = nil, -- Global mappings. Specify a buffer number for buffer local mappings
--       silent = true, -- use `silent` when creating keymaps
--       noremap = true, -- use `noremap` when creating keymaps
--       nowait = true, -- use `nowait` when creating keymaps
--     })
--   end,
-- }
