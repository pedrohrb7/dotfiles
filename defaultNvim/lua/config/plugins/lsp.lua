return {
  'neovim/nvim-lspconfig',
  event = { 'BufReadPre', 'BufNewFile' },
  dependencies = {
    'hrsh7th/cmp-nvim-lsp',
    { 'antosha417/nvim-lsp-file-operations', config = true },
  },
  config = function()
    local lspconfig = require('lspconfig')
    local cmp_nvim_lsp = require('cmp_nvim_lsp')

    local keymap = vim.keymap -- for conciseness

    local opts = { noremap = true, silent = true }

    -- used to enable autocompletion (assign to every lsp server config)
    local capabilities = cmp_nvim_lsp.default_capabilities()

    -- Change the Diagnostic symbols in the sign column (gutter)
    -- (not in youtube nvim video)
    -- local signs = { Error = ' ', Warn = ' ', Hint = '󰠠 ', Info = ' ' }
    -- for type, icon in pairs(signs) do
    --   local hl = 'DiagnosticSign' .. type
    --   -- vim.fn.sign_define(hl, { text = icon, texthl = hl, numhl = '' })
    --   vim.diagnostic.config(hl, { text = icon, texthl = hl, numhl = '' })
    -- end

    lspconfig['dockerls'].setup({
      capabilities = capabilities,
    })

    lspconfig['terraformls'].setup({
      capabilities = capabilities,
    })

    lspconfig['jsonls'].setup({
      capabilities = capabilities,
    })

    lspconfig['ts_ls'].setup({
      filetypes = { 'typescript', 'javascript', 'javascriptreact', 'typescriptreact', 'vue' },
      capabilities = capabilities,
      root_dir = lspconfig.util.root_pattern('package.json'),
      single_file_support = false,
      settings = {
        typescript = {
          tsserver = {
            useSyntaxServer = false,
          },
          inlayHints = {
            includeInlayParameterNameHints = 'all',
            includeInlayParameterNameHintsWhenArgumentMatchesName = true,
            includeInlayFunctionParameterTypeHints = true,
            includeInlayVariableTypeHints = true,
            includeInlayVariableTypeHintsWhenTypeMatchesName = true,
            includeInlayPropertyDeclarationTypeHints = true,
            includeInlayFunctionLikeReturnTypeHints = true,
            includeInlayEnumMemberValueHints = true,
          },
        },
      },
    })

    -- lspconfig['intelephense'].setup({
    --   capabilities = capabilities,
    --   on_attach = on_attach,
    --   cmd = { 'intelephense', '--stdio' },
    --   filetypes = { 'php', 'blade' },
    --   root_pattern = { 'composer.json', '.git' },
    -- })
    -- lspconfig['tailwindcss'].setup({
    --   capabilities = capabilities,
    --   on_attach = on_attach,
    -- })

    -- lspconfig['volar'].setup({
    --   capabilities = capabilities,
    --   filetypes = { 'typescript', 'javascript', 'javascriptreact', 'typescriptreact', 'vue' },
    --   init_options = {
    --     vue = {
    --       hybridMode = false,
    --     },
    --     typescript = {
    --       tsdk = '~/.local/share/lazynvim/mason/packages/vue-language-server/node_modules/typescript/lib/',
    --     },
    --   },
    --   settings = {
    --     typescript = {
    --       inlayHints = {
    --         enumMemberValues = {
    --           enabled = true,
    --         },
    --         functionLikeReturnTypes = {
    --           enabled = true,
    --         },
    --         propertyDeclarationTypes = {
    --           enabled = true,
    --         },
    --         parameterTypes = {
    --           enabled = true,
    --           suppressWhenArgumentMatchesName = true,
    --         },
    --         variableTypes = {
    --           enabled = true,
    --         },
    --       },
    --     },
    --   },
    -- })

    lspconfig['cssls'].setup({
      capabilities = capabilities,
    })

    -- lspconfig['graphql'].setup({
    --   capabilities = capabilities,
    --   filetypes = { 'graphql', 'gql', 'typescriptreact', 'javascriptreact' },
    -- })

    lspconfig['emmet_ls'].setup({
      capabilities = capabilities,
      filetypes = { 'html', 'typescriptreact', 'javascriptreact', 'css', 'sass', 'scss', 'less' },
    })

    lspconfig['lua_ls'].setup({
      capabilities = capabilities,
      settings = {
        Lua = {
          -- make the language server recognize "vim" global
          diagnostics = {
            globals = { 'vim' },
          },
          completion = {
            callSnippet = 'Replace',
          },
        },
      },
    })
  end,
}
