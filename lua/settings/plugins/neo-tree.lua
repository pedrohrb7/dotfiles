return {
    "nvim-neo-tree/neo-tree.nvim",
    branch = "v3.x",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "nvim-tree/nvim-web-devicons", -- not strictly required, but recommended
      "MunifTanjim/nui.nvim",
    },

    config = function()
      local neoTree = require('neo-tree')
      neoTree.setup({
        window = {
          position = "right",
          mappings = {
            ["<cr>"] = "open_tabnew",
          },
        },
        filesystem = {
          filtered_items = {
            hide_dotfiles = false,
            hide_gitignored = false,
          },
          follow_current_file = {
            enabled = false,
          }
        },
        buffers = {
          follow_current_file = {
            enabled = true,
          }
        }
      })

      vim.keymap.set('n', '-', function()
        local reveal_file = vim.fn.expand('%:p')
        if (reveal_file == '') then
          reveal_file = vim.fn.getcwd()
        else
          local f = io.open(reveal_file, "r")
          if (f) then
            f.close(f)
          else
            reveal_file = vim.fn.getcwd()
          end
        end
        require('neo-tree.command').execute({
          reveal_file = reveal_file, -- path to file or folder to reveal
          reveal_force_cwd = true,   -- change cwd without asking if needed
        })
      end,
      { desc = "Open neo-tree at current file or working directory" }
      )

    -- set keymaps
    local keymap = vim.keymap -- for conciseness

    keymap.set("n", "<leader>ee", "<cmd>Neotree toggle<CR>", { desc = "Toggle file explorer" }) -- toggle file explorer
    keymap.set("n", "<leader>ec", "<cmd>NvimTreeCollapse<CR>", { desc = "Collapse file explorer" }) -- collapse file explorer
    end
}
