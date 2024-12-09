return {
  'nvim-treesitter/nvim-treesitter',
  build = ':TSUpdate',

  config = function()
    local configs = require('nvim-treesitter.configs')
    local ensure_installed = {
      'angular',
      'jsonc',
      'php',
      'pug',
      'vue',
      'scss',
      'c',
      'lua',
      'luadoc',
      'printf',
      'vim',
      'vimdoc',
      'css',
      'tsx',
      'typescript',
      'javascript',
      'dockerfile',
      'yaml',
      'html',
      'php_only',
    }
    configs.setup({
      ensure_installed = ensure_installed,
      auto_install = true,
      sync_install = true,
      highlight = { enable = true },
      indent = { enable = true },
    })

    local parser_config = require('nvim-treesitter.parsers').get_parser_configs()
    parser_config.blade = {
      install_info = {
        url = 'https://github.com/EmranMR/tree-sitter-blade',
        files = { 'src/parser.c' },
        branch = 'main',
      },
      filetype = 'blade',
    }
    vim.filetype.add({
      pattern = {
        ['.*%.blade%.php'] = 'blade',
      },
    })
  end,
}
