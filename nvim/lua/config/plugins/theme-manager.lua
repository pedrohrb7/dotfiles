return {
  'zaldih/themery.nvim',
  lazy = false,
  config = function()
    require('themery').setup({
      themes = {
        'nord',
        'onedark_dark',
        'tokyonight',
        'solarized',
        'fluoromachine',
        'cyberdream',
        'github_dark',
        'onedark',
        'rose-pine',
        'moonfly',
      },
    })
  end,
}
