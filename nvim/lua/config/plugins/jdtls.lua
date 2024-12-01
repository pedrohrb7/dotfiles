return {
  "mfussenegger/nvim-jdtls",
  opts = {
    -- cmd = {'/path/to/jdt-language-server/bin/jdtls'},
    root_dir = vim.fs.dirname(vim.fs.find({ "gradlew", ".git", "mvnw" }, { upward = true })[1]),
  },
  config = function()
    local jdtls = require("jdtls")
    jdtls.start_or_attach(opts)
  end,
}
