return {
  'jay-babu/mason-nvim-dap.nvim',
  config = function()
    -- ensure the java debug adapter is installed
    require('mason-nvim-dap').setup({
      ensure_installed = { 'java-debug-adapter', 'java-test' },
    })
  end,
}
