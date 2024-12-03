return {
  'williamboman/mason.nvim',
  dependencies = {
    'williamboman/mason-lspconfig.nvim',
    'WhoIsSethDaniel/mason-tool-installer.nvim',
  },
  lazy = false,
  config = function()
    local mason = require('mason')
    local mason_lspconfig = require('mason-lspconfig')
    local mason_tool_installer = require('mason-tool-installer')

    mason.setup({
      ui = {
        border = 'rounded',
        icons = {
          package_installed = '✓',
          package_pending = '➜',
          package_uninstalled = '✗',
        },
      },
    })

    mason_lspconfig.setup({
      ensure_installed = {
        'jsonls',
        'lua_ls',
        'terraformls',
        'dockerls',
        'tailwindcss',
        'cssls',
        'sqls',
        -- 'phpcs',
        -- 'php-cs-fixer',
        -- 'phpactor',
        'intelephense',
        'eslint',
        'ts_ls',
        'graphql',
        'emmet_ls',
        'prismals',
        'kotlin_language_server',
      },

      automatic_installation = true,
    })

    mason_tool_installer.setup({
      ensure_installed = {
        'prettier', -- prettier formatter
        'stylua', -- lua formatter
        'pylint',
        'cssls',
        'ktlint',
        'intelephense',
        'lua-language-server',
        'editorconfig-checker',
        { 'eslint_d', version = '13.1.2' },
      },
    })
  end,
}
