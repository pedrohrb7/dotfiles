return {
  {
    "nvim-tree/nvim-web-devicons",
    config = function()
      local nwdevicons = require("nvim-web-devicons")

      nwdevicons.setup({
        color_icons = true,
      })
    end,
  },
  {
    "echasnovski/mini.nvim",
    version = "*",
  },
}
