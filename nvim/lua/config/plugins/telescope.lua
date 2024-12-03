return {
  'nvim-telescope/telescope.nvim',
  branch = '0.1.x',
  dependencies = {
    'nvim-lua/plenary.nvim',
    { 'nvim-telescope/telescope-fzf-native.nvim', build = 'make' },
    'nvim-tree/nvim-web-devicons',
    'folke/todo-comments.nvim',
    'nvim-telescope/telescope-ui-select.nvim',
    'nvim-telescope/telescope-media-files.nvim',
  },
  config = function()
    local telescope = require('telescope')
    local actions = require('telescope.actions')
    local transform_mod = require('telescope.actions.mt').transform_mod

    local trouble = require('trouble')
    local trouble_telescope = require('trouble.sources.telescope')

    -- or create your custom action
    local custom_actions = transform_mod({
      open_trouble_qflist = function(prompt_bufnr)
        trouble.toggle('quickfix')
      end,
    })

    telescope.setup({
      defaults = {
        path_display = { 'smart' },
        file_ignore_patterns = {
          'node_modules',
          '.next',
          'dist',
          'bundle',
          '.git',
          '.yarn',
        },
        mappings = {
          i = {
            ['<C-k>'] = actions.move_selection_previous, -- move to prev result
            ['<C-j>'] = actions.move_selection_next, -- move to next result
            ['<C-q>'] = actions.send_selected_to_qflist + custom_actions.open_trouble_qflist,
            ['<C-t>'] = trouble_telescope.smart_open_with_trouble,
          },
        },
      },
      pickers = {
        find_files = {
          theme = 'dropdown',
          hidden = true,
        },
      },
      extensions = {
        media_files = {
          -- filetypes whitelist
          -- defaults to {"png", "jpg", "mp4", "webm", "pdf"}
          filetypes = { 'png', 'webp', 'jpg', 'jpeg', 'pdf', 'pdf' },
          -- find command (defaults to `fd`)
          find_cmd = 'rg',
        },
        ['ui-select'] = {
          require('telescope.themes').get_dropdown({}),
        },
      },
    })

    telescope.load_extension('fzf')
    telescope.load_extension('ui-select')
    telescope.load_extension('noice')
    telescope.load_extension('media_files')
  end,
}
