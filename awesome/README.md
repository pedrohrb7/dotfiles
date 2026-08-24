# awesome config

```
rc.lua                      -- carrega os módulos abaixo, nessa ordem
config/
  handle-errors.lua         -- notifica erros de startup/runtime (naughty)
  notifications.lua         -- presets e espaçamento do naughty
  vars.lua                  -- SUPER/ALT, terminal/browser/fileManager, ordem dos layouts
  theme.lua                 -- tema único (beautiful init)
  wibar.lua                 -- wibar por tela: tags, layoutbox, clock, systray (widgets padrão do awesome)
  keys/
    global.lua               -- atalhos globais (launchers, tags, layout, foco)
    client.lua                -- atalhos e botões por cliente (usados em rules.lua)
  rules.lua                 -- awful.rules.rules (floating, titlebars, placement)
  signals.lua                -- sinais de client (manage, titlebars, foco)
  autostart.lua              -- nm-applet/blueman-applet/pasystray/picom/pipewire
  styles/                    -- paleta de cores compartilhada
```

