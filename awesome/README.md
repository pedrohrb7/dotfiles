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

## Layout do teclado (us/br)

`Control + Alt + Space` alterna entre os grupos XKB `us` e `br`. Os dois layouts
são definidos como padrão do servidor X em `/etc/X11/xorg.conf.d/00-keyboard.conf`:

```
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "us,br"
EndSection
```

Não use `setxkbmap` no `.xinitrc`/`.xprofile`: ele só altera o keymap em runtime,
e qualquer teclado conectado depois (USB, Bluetooth) faz o Xorg voltar ao padrão
do servidor, deixando só um grupo e quebrando a troca.
