pcall(function()
  dofile(vim.g.base46_cache .. "syntax")
  dofile(vim.g.base46_cache .. "treesitter")
end)

return {
  ensure_installed = {
    "angular",
    "jsonc",
    "kotlin",
    "php",
    "prisma",
    "pug",
    "vue",
    "scss",
    "xml",
    "c",
    "lua",
    "luadoc",
    "vim",
    "vimdoc",
    "css",
    "tsx",
    "typescript",
    "dockerfile",
    "yaml",
    "javascript",
    "html",
  },

  highlight = {
    enable = true,
    use_languagetree = true,
  },

  indent = { enable = true },
}
