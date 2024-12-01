return {
  "mfussenegger/nvim-lint",
  event = "VeryLazy",
  config = function()
    local lint = require("lint")

    lint.linters_by_ft = {
      javascript = { "eslint_d" },
      typescript = { "eslint_d" },
      javascriptreact = { "eslint_d" },
      typescriptreact = { "eslint_d" },
      java = { "trivy", "checkstyle" },
      kotlin = { "klint" },
      -- editorconfig = { "editorconfig-checker" },
    }
    local lint_augroup = vim.api.nvim_create_augroup("lint", { clear = true })

    vim.api.nvim_create_autocmd({ "BufEnter", "BufWritePost", "InsertLeave" }, {
      group = lint_augroup,
      callback = function()
        lint.try_lint()
      end,
    })

    -- TODO: need to know how to put this keymap at keymap.lua
    vim.keymap.set("n", "<leader>ll", function()
      lint.try_lint()
    end, { desc = "Trigger linting in current buffer" })
  end,
}
