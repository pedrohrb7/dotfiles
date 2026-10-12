# awesome config

```
rc.lua                      -- carrega os módulos abaixo, nessa ordem
.luarc.json                 -- lua-language-server: globais do awesome (C API) e lib em /usr/share/awesome/lib; ignora rc_default.lua
config/
  handle-errors.lua         -- notifica erros de startup/runtime (naughty)
  notifications.lua         -- presets e espaçamento do naughty
  battery.lua               -- avisos de bateria baixa/crítica (naughty, sem widget)
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

O greeter do LightDM com o indicador `~layout` (em
`/etc/lightdm/lightdm-gtk-greeter.conf`) aplica um único layout no servidor X antes
do login, e a sessão herda esse keymap com só um grupo. Por isso
`config/keyboard.lua` confere os grupos ao iniciar o awesome e a cada sinal
`xkb::map_changed`, e roda `setxkbmap -layout us,br` quando falta algum. Atenção:
`setxkbmap -query` não serve para diagnosticar isso, porque mostra a propriedade
`_XKB_RULES_NAMES` e não o keymap real. Use
`awesome-client 'return awesome.xkb_get_group_names()'`, que deve conter `br:2`.

## Avisos de bateria

`config/battery.lua` lê `/sys/class/power_supply/*/uevent` a cada 60s e, enquanto
descarrega, mostra uma notificação normal em 20% (`LOW`) e uma crítica fixa em 10%
(`CRITICAL`), cada uma uma única vez. Ligar o carregador fecha o aviso e rearma os
dois limites. Com mais de uma bateria, a porcentagem é a soma da energia de todas.

No carregador, ao chegar em 100% (status `Full`, ou 100% com `Not charging` para
fuel gauges que nunca reportam `Full`) aparece uma notificação de baixa prioridade
(preset `low`), uma vez só; ela só rearma depois de desconectar o carregador. Se a
bateria já estiver cheia quando o awesome inicia, nada é mostrado. Com limite de
carga abaixo de 100% (ex.: ThinkPad em 80%) essa notificação nunca aparece.

Não precisa instalar nenhum pacote: a leitura vem direto do sysfs do kernel (driver
ACPI `battery`/`ac`, já presente no kernel do Void) e usa só `sh` e `cat`. Não
depende de `acpi`, `upower` nem `acpid`.

`Super+Shift+T` mostra sob demanda uma notificação com o nível atual e o estado
(`Charging`, `Fully charged`, `On battery` ou `Plugged in, not charging`, este último
quando há limite de carga no carregador) via `battery.show()`; apertar de novo
substitui a anterior.

Uma bateria que reporta 0% enquanto o notebook roda nela é tratada como leitura
inválida (fuel gauge travado) e não gera aviso. Para testar sem descarregar, aponte
o módulo para uevents falsos:

```
awesome-client "require('config.battery').init({ path = '/tmp/ps', timeout = 2 })"
```

onde `/tmp/ps/AC/uevent` e `/tmp/ps/BAT0/uevent` contêm linhas
`POWER_SUPPLY_*` como as de `/sys/class/power_supply`.
