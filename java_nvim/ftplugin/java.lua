-- local config = {
--   cmd = { vim.fn.expand '~/.local/share/jnvim/mason/bin/jdtls' },
--   root_dir = vim.fs.dirname(vim.fs.find({ 'gradlew', '.git', 'mvnw' }, { upward = true })[1]),
-- }
-- require('jdtls').start_or_attach(config)

local workspace_path = '/home/pedro/.local/share/jnvim/jdtls_workspace'
local project_name = vim.fn.fnamemodify(vim.fn.getcwd(), ':p:h:t')
local workspace_dir = workspace_path .. project_name

local status, jdtls = pcall(require, 'jdtls')
if not status then
  return
end

local extendedClientCapabilities = jdtls.extendedClientCapabilities

-- local jdtls_install = require('mason-registry').get_package('jdtls'):get_install_path()
-- local java_agent = jdtls_install .. '/lombok.jar'

local config = {
  -- The command that starts the language server
  -- See: https://github.com/eclipse/eclipse.jdt.ls#running-from-the-command-line
  cmd = {
    'java',
    '-Declipse.application=org.eclipse.jdt.ls.core.id1',
    '-Dosgi.bundles.defaultStartLevel=4',
    '-Declipse.product=org.eclipse.jdt.ls.core.product',
    '-Dlog.protocol=true',
    '-Dlog.level=ALL',
    '-Xmx1g',
    '--add-modules=ALL-SYSTEM',
    '--add-opens',
    'java.base/java.util=ALL-UNNAMED',
    '--add-opens',
    'java.base/java.lang=ALL-UNNAMED',
    -- '-javaagent',
    -- java_agent,
    '-jar',
    '/home/pedro/.local/share/jnvim/mason/packages/jdtls/plugins/org.eclipse.equinox.launcher_1.7.0.v20250331-1702.jar',
    '-configuration',
    '/home/pedro/.local/share/jnvim/mason/packages/jdtls/config_linux',
    '-data',
    workspace_dir,
  },

  root_dir = vim.fs.root(0, { '.git', 'mvnw', 'gradlew' }),
  -- root_dir = require('jdtls.setup').find_root { '.git', 'mvnw', 'gradlew', 'pom.xml', 'build.gradle' },

  settings = {
    java = {
      signatureHelp = { enabled = true },
      extendedClientCapabilities = extendedClientCapabilities,
      maven = {
        downloadSources = true,
      },
      referencesCodeLens = {
        enabled = true,
      },
      references = {
        includeDecompiledSources = true,
      },
      inlayHints = {
        parameterNames = {
          enabled = 'all', -- literals, all, none
        },
      },
      format = {
        enabled = false,
      },
    },
  },

  -- Language server `initializationOptions`
  -- You need to extend the `bundles` with paths to jar files
  -- if you want to use additional eclipse.jdt.ls plugins.
  --
  -- See https://github.com/mfussenegger/nvim-jdtls#java-debug-installation
  --
  -- If you don't plan on using the debugger or other eclipse.jdt.ls plugins you can remove this
  -- init_options = {
  --   bundles = {}
  -- },
}

require('jdtls').start_or_attach(config)

vim.keymap.set('n', '<leader>co', "<Cmd>lua require'jdtls'.organize_imports()<CR>", { desc = 'Organize Imports' })
vim.keymap.set('n', '<leader>crv', "<Cmd>lua require('jdtls').extract_variable()<CR>", { desc = 'Extract Variable' })
vim.keymap.set('v', '<leader>crv', "<Esc><Cmd>lua require('jdtls').extract_variable(true)<CR>", { desc = 'Extract Variable' })
vim.keymap.set('n', '<leader>crc', "<Cmd>lua require('jdtls').extract_constant()<CR>", { desc = 'Extract Constant' })
vim.keymap.set('v', '<leader>crc', "<Esc><Cmd>lua require('jdtls').extract_constant(true)<CR>", { desc = 'Extract Constant' })
-- vim.keymap.set('v', '<leader>crm', "<Esc><Cmd>lua require('jdtls').extract_method(true)<CR>", { desc = 'Extract Method' })
