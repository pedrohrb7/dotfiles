return {
  "lukas-reineke/indent-blankline.nvim",
  main = "ibl",
  opts = {},
  config = function()
    local ibl = require("ibl")
    local vm = vim
    local highlight = {
      "RainbowRed",
      "RainbowYellow",
      "RainbowBlue",
      "RainbowOrange",
      "RainbowGreen",
      "RainbowViolet",
      "RainbowCyan",
    }

    local hooks = require("ibl.hooks")
    -- create the highlight groups in the highlight setup hook, so they are reset
    -- every time the colorscheme changes
    hooks.register(hooks.type.HIGHLIGHT_SETUP, function()
      vm.api.nvim_set_hl(0, "RainbowRed", { fg = "#E06C75" })
      vm.api.nvim_set_hl(0, "RainbowYellow", { fg = "#E5C07B" })
      vm.api.nvim_set_hl(0, "RainbowBlue", { fg = "#61AFEF" })
      vm.api.nvim_set_hl(0, "RainbowOrange", { fg = "#D19A66" })
      vm.api.nvim_set_hl(0, "RainbowGreen", { fg = "#98C379" })
      vm.api.nvim_set_hl(0, "RainbowViolet", { fg = "#C678DD" })
      vm.api.nvim_set_hl(0, "RainbowCyan", { fg = "#56B6C2" })
      vm.api.nvim_set_hl(0, "RainbowLavender", { fg = "#45707a" })
    end)

    vm.g.rainbow_delimiters = { highlight = highlight }
    hooks.register(hooks.type.SCOPE_HIGHLIGHT, hooks.builtin.scope_highlight_from_extmark)
    ibl.setup({
      debounce = 100,
      indent = { highlight = highlight },
      -- whitespace = { highlight = { "Whitespace", "NonText" } },
    })
  end,
}
