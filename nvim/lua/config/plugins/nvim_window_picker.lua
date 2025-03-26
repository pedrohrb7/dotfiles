return {
  's1n7ax/nvim-window-picker',
  name = 'window-picker',
  event = 'VeryLazy',
  version = '2.*',
  config = function()
    local wp = require('window-picker')

    local colors = {
      bg = '#24283b',
      bg_dark = '#1f2335',
      bg_dark1 = '#1b1e2d',
      bg_highlight = '#292e42',
      blue = '#7aa2f7',
      blue0 = '#3d59a1',
      blue1 = '#2ac3de',
      blue2 = '#0db9d7',
      blue5 = '#89ddff',
      blue6 = '#b4f9f8',
      blue7 = '#394b70',
      comment = '#565f89',
      cyan = '#7dcfff',
      dark3 = '#545c7e',
      dark5 = '#737aa2',
      fg = '#c0caf5',
      fg_dark = '#a9b1d6',
      fg_gutter = '#3b4261',
      green = '#9ece6a',
      green1 = '#73daca',
      green2 = '#41a6b5',
      magenta = '#bb9af7',
      magenta2 = '#ff007c',
      orange = '#ff9e64',
      purple = '#9d7cd8',
      red = '#f7768e',
      red1 = '#db4b4b',
      teal = '#1abc9c',
      terminal_black = '#414868',
      yellow = '#e0af68',
      git = {
        add = '#449dab',
        change = '#6183bb',
        delete = '#914c54',
      },
    }
    -- Debug: Verifique se colors está definido corretamente
    print(vim.inspect(colors))
    local options = {
      -- when you go to window selection mode, status bar will show one of
      -- following letters on them so you can use that letter to select the window
      selection_chars = 'ABCDEFGHIJKLMNOPQRSvUTXYZ',

      -- You can pass in the highlight name or a table of content to set as
      -- Tokyonight palette
      -- highlight
      highlights = {
        statusline = {
          focused = {
            fg = '#ededed',
            bg = colors.dark5,
            bold = true,
          },
          unfocused = {
            fg = '#ededed',
            bg = colors.magenta2,
            bold = true,
          },
        },
        winbar = {
          focused = {
            fg = '#ededed',
            bg = '#e35e4f',
            bold = true,
          },
          unfocused = {
            fg = '#ededed',
            bg = colors.green1,
            bold = true,
          },
        },
      },
    }

    wp.setup(options)
  end,
}
