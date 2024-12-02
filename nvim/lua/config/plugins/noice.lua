return {
  'folke/noice.nvim',
  event = 'VeryLazy',
  opts = {},
  dependencies = {
    'MunifTanjim/nui.nvim',
    'rcarriga/nvim-notify',
  },

  config = function()
    local noice = require('noice')

    noice.setup({
      presets = {
        bottom_search = false, -- This apply search word as same style as cmdLine
      },
    })
  end,
}
