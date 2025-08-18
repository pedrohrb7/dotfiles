return {
  "folke/trouble.nvim",
  opts = {
    modes = {
      diagnostics_buffer = {
        mode = "diagnostics", -- inherit from diagnostics mode
        filter = { buf = 0 }, -- filter diagnostics to the current buffer
      },
      preview_float = {
        mode = "diagnostics",
        preview = {
          type = "float",
          relative = "editor",
          border = "rounded",
          title = "Preview",
          title_pos = "center",
          position = { 0, -2 },
          size = { width = 0.3, height = 0.3 },
          zindex = 200,
        },
      },
    },
  }, -- for default options, refer to the configuration section for custom setup.
}
