return {
  "goolord/alpha-nvim",
  dependencies = {
    "nvim-tree/nvim-web-devicons",
  },

  config = function()
    local alpha = require("alpha")
    local dashboard = require("alpha.themes.startify")

    local logo = {
      {
        [[       ,                              ]],
        [[       \`-._           __             ]],
        [[        \\  \-..____,.'  `.           ]],
        [[         :  )       :      :\         ]],
        [[          ;'        '   ;  | :        ]],
        [[          )..      .. .:.`.; :        ]],
        [[         /::...  .:::...   ` ;        ]],
        [[         `:o>   /\o_>        : `.     ]],
        [[        `-`.__ ;   __..--- /:.   \    ]],
        [[        === \_/   ;=====_.':.     ;   ]],
        [[         ,/'`--'...`--....        ;   ]],
        [[              ;                    ;  ]],
        [[          . '                       ; ]],
        [[        .'     ..     ,      .       ;]],
        [[       :       ::..  /      ;::.     |]],
        [[      /      `.;::.  |       ;:..    ;]],
        [[     :         |:.   :       ;:.    ; ]],
        [[     :         ::     ;:..   |.    ;  ]],
        [[      :       :;      :::....|     |  ]],
        [[      /\     ,/ \      ;:::::;     ;  ]],
        [[    .:. \:..|    :     ; '.--|     ;  ]],
        [[   ::.  :''  `-.,,;     ;'   ;     ;  ]],
        [[.-'. _.'\      / `;      \,__:      \ ]],
        [[`---'    `----'   ;      /    \,.,,,/ ]],
        [[                   `----`             ]],
        [[                                      ]],
      },
    }

    local opts = {
      position = "center",
      hl = "Type",
    }

    dashboard.leader = "\\"
    dashboard.section.header.val = logo
    dashboard.section.header.opts = opts
    dashboard.section.opts = opts
    alpha.setup(dashboard.opts)
  end,
}
