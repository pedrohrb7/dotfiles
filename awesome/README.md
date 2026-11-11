# awesome config

```
rc.lua                      -- carrega os módulos abaixo, nessa ordem
.luarc.json                 -- lua-language-server ao abrir só awesome/: globais do awesome (C API) e lib em /usr/share/awesome/lib; ignora rc_default.lua
                            -- (abrindo ~/dotfiles, vale o ../.luarc.json, que repete esses globais e a lib)
config/
  handle-errors.lua         -- notifica erros de startup/runtime (naughty)
  notifications.lua         -- presets e espaçamento do naughty
  battery.lua               -- avisos de bateria baixa/crítica (naughty, sem widget)
  brightness.lua            -- brilho: backlight (brightnessctl) ou monitor por DDC/CI (ddcutil), usado pelo widget e pelas teclas
  vars.lua                  -- SUPER/ALT, terminal/browser/fileManager (nautilus, Super+E), ordem dos layouts
  theme.lua                 -- tema único (beautiful init)
  wibar.lua                 -- wibar por tela: tags, layoutbox, clock, systray, brilho/mic/volume (rede e Bluetooth desativados: ficam no conky)
  widgets/                  -- widgets da wibar (network.lua e bluetooth.lua ficam no repo, mas fora da wibar)
  keys/
    global.lua               -- atalhos globais (launchers, tags, layout, foco)
    client.lua                -- atalhos e botões por cliente (usados em rules.lua)
  rules.lua                 -- awful.rules.rules (floating, titlebars, placement, conky fixo no desktop e sem tag, para não marcar a tag 1 como ocupada)
  signals.lua                -- sinais de client (manage, titlebars, foco)
  screens.lua                -- hotplug de monitor: roda o autorandr ao conectar/desconectar e leva as janelas do monitor que saiu para a primeira tag vazia da tela principal
  autostart.lua              -- layout de monitores (autorandr, ver ../setup/README.md), pipewire (se o socket não existe)/picom/conky (ver ../conky/README.md), Nautilus como app padrão de pastas (inode/directory no ~/.config/mimeapps.list, senão o mimeinfo.cache do sistema escolhe o kitty e abre um terminal)
  styles/                    -- paleta de cores compartilhada
.xinitrc                    -- carrega .Xresources, exporta XCURSOR_* e inicia o awesome
.xprofile                   -- lido pelo LightDM antes do awesome: bus D-Bus da sessão, gnome-keyring, picom, slstatus (link em ~/.xprofile)
.Xresources                 -- tema e tamanho do cursor (Xcursor.*)
icons/default/index.theme   -- tema de cursor padrão do X11 (link em ~/.icons/default/)
gtk-3.0/settings.ini        -- tema de cursor dos apps GTK (link em ~/.config/gtk-3.0/)
```

## Layout do teclado (us/br)

`Control + Alt + Space` alterna entre os grupos XKB `us` e `br`. Os dois layouts
são definidos como padrão do servidor X em `/etc/X11/xorg.conf.d/00-keyboard.conf`,
instalado por `setup/hardware.sh` a partir de `xorg_config/keyboard.conf`:

```
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "us,br"
    Option "XkbModel" "pc105+inet"
    Option "XkbOptions" "terminate:ctrl_alt_bksp"
EndSection
```

Vale a partir do próximo início do X (logout ou reboot).

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

## Cursor do mouse (Bibata Rainbow Modern)

O cursor é o [Bibata Cursor Rainbow](https://github.com/ful1e5/Bibata_Cursor_Rainbow),
variante `Bibata-Rainbow-Modern`, tamanho 24. O tema em si **não fica no repo**:
extraído ele ocupa ~261 MB (o `.tar.gz` tem ~19 MB). Só as configs são versionadas.

### Instalar em uma máquina nova

1. Baixe `Bibata-Rainbow-Modern.tar.gz` na página de releases:
   <https://github.com/ful1e5/Bibata_Cursor_Rainbow/releases>
2. Extraia o tema e crie os links das configs:

```sh
mkdir -p ~/.icons/default ~/.config/gtk-3.0
tar -xzf ~/Bibata-Rainbow-Modern.tar.gz -C ~/.icons   # cria ~/.icons/Bibata-Rainbow-Modern/

ln -s ~/dotfiles/awesome/.xinitrc                  ~/.xinitrc
ln -s ~/dotfiles/awesome/.xprofile                 ~/.xprofile
ln -s ~/dotfiles/awesome/.Xresources               ~/.Xresources
ln -s ~/dotfiles/awesome/icons/default/index.theme ~/.icons/default/index.theme
ln -s ~/dotfiles/awesome/gtk-3.0/settings.ini      ~/.config/gtk-3.0/settings.ini
```

3. Saia do awesome e rode `startx` de novo. Apps que já estavam abertos só pegam o
   cursor novo depois de reabertos.

### Onde o tema é configurado

| Arquivo                     | Quem lê                               |
| --------------------------- | ------------------------------------- |
| `.Xresources`               | X11/Xlib (`Xcursor.theme`, `Xcursor.size`), via `xrdb -merge` no `.xinitrc` |
| `.xinitrc`                  | `XCURSOR_THEME`/`XCURSOR_SIZE` para apps que leem variáveis de ambiente |
| `icons/default/index.theme` | tema "default" do libXcursor (fallback de qualquer app X11) |
| `gtk-3.0/settings.ini`      | apps GTK 3                            |
| `rc.lua`                    | `root.cursor("left_ptr")`: cursor no fundo da tela (sem ele aparece um "X") |

Para trocar o tema ou o tamanho, altere o nome/número **nos quatro primeiros
arquivos**. Para aplicar o `.Xresources` sem reiniciar o X, rode
`xrdb -merge ~/.Xresources`.

## Sessão D-Bus (sftp/ftp no Nautilus e no Thunar)

O LightDM roda `/etc/lightdm/Xsession`, que faz `source` do `~/.xprofile` e depois
`exec awesome`. Nada nesse caminho inicia um bus D-Bus de sessão. Sem o
`dbus-launch` no `.xprofile`, o primeiro programa que precisa do bus (o
`gnome-keyring-daemon --start`) cria um por **X11 autolaunch**, e
`DBUS_SESSION_BUS_ADDRESS` nunca é exportada para o awesome e os filhos dele.

A maioria dos apps acha esse bus pelo autolaunch, mas o módulo cliente do gvfs não:
sem a variável, o GIO cai no VFS local (`GLocalVfs`) e `sftp://`, `ftp://`, `smb://`
etc. dão `Operation not supported` no Nautilus, no Thunar e no `gio`, mesmo com o
`gvfs` instalado e o `gvfsd` rodando.

Por isso o `.xprofile`, antes do `gnome-keyring-daemon`:

1. roda `dbus-launch --sh-syntax --exit-with-x11` e exporta o endereço (o bus morre
   junto com o X);
2. depois do keyring, roda `dbus-update-activation-environment DISPLAY XAUTHORITY
   SSH_AUTH_SOCK`, para os serviços ativados pelo bus (`gvfsd-sftp`) usarem o agente
   SSH e o display da sessão.

Vale a partir do próximo login. Conferir:

```
echo $DBUS_SESSION_BUS_ADDRESS    # deve ter unix:path=...
gio info sftp://usuario@host/     # "not mounted" está certo; "Operation not supported" é o bug
```

Para corrigir uma sessão já aberta sem relogar, injete o endereço do bus que existe
(o do `gvfsd`) no ambiente do awesome e reabra os gerenciadores. Vale só para apps
abertos pelo awesome dali em diante; terminais já abertos continuam sem a variável:

```
BUS=$(tr '\0' '\n' < /proc/$(pgrep -x gvfsd)/environ | sed -n 's/^DBUS_SESSION_BUS_ADDRESS=//p')
DBUS_SESSION_BUS_ADDRESS=$BUS awesome-client "require('lgi').GLib.setenv('DBUS_SESSION_BUS_ADDRESS', '$BUS', true)"
pkill -x thunar; pkill -x nautilus
```

Para conectar: `Ctrl+L` e `sftp://usuario@host/` ou `ftp://host/`, nos dois
gerenciadores. No Nautilus também há *Outros locais* > *Conectar ao servidor*.
Favoritos em `~/.config/gtk-3.0/bookmarks` (arquivo local, fora do repo) aparecem
na barra lateral de ambos.

Servidor com IPv6 quebrado (ex.: `ftp.gnu.org` na porta 21) faz o gvfs esperar o
timeout de TCP do IPv6 (~2 min) antes de tentar o IPv4. Isso é do servidor, não da
sessão: `curl -4`/`curl -6 ftp://host/` mostra a diferença.

## Monitor conectado/desconectado

### Hotplug

Quem reage ao cabo é o próprio awesome, não a regra udev do autorandr
(`/usr/lib/udev/rules.d/40-monitor-hotplug.rules`). O driver da NVIDIA, que
controla a `HDMI-1-0`, não emite evento DRM no udev (`udevadm monitor
--subsystem-match=drm` fica mudo), então a regra nunca roda. Sem ela, a saída
desconectada continua configurada no X (`HDMI-1-0 disconnected 1920x1080+1920+0`),
o awesome continua vendo duas telas e nada acontece.

O awesome recebe a mudança pelo RandR como o sinal global `screen::change`
(`HDMI-1-0 Connected`/`Disconnected`). `config/screens.lua` escuta esse sinal e,
0,5 s depois do último evento (um plug gera vários seguidos), roda
`autorandr --change --default default` como o usuário, o mesmo comando do
`autostart.lua` (que chama `screens.apply_layout()`). Ao desconectar, o autorandr
desliga a saída e o awesome remove a tela.

### Janelas do monitor que saiu

Por padrão, o awesome 4.3 apaga as tags de uma tela que sai e joga todas as
janelas dela na **tag 1** de outra tela, misturadas com o que já estava lá.

`config/screens.lua` intercepta o sinal `removal-pending` (a última chance que o
awesome dá antes desse fallback) e move **todas** as janelas da tela que saiu,
de todas as tags dela, para a **primeira tag vazia da tela principal**
(`screen.primary`; se a própria principal for a que saiu, qualquer outra tela com
tags). Se nenhuma tag estiver vazia, vai para a última tag. Janelas flutuantes são
trazidas para dentro da tela (`no_offscreen`). Uma notificação `low` informa
quantas janelas foram movidas e para qual tag. Nada muda ao reconectar: o monitor
volta com tags novas e vazias.

Testar sem desconectar o cabo, com uma tela falsa:

```
awesome-client '_G.fake = screen.fake_add(3840, 0, 800, 600)'
# mova uma janela para uma tag da tela nova e depois:
awesome-client '_G.fake:fake_remove()'
```

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

## Brilho

`config/brightness.lua` detecta o backend uma vez, ao iniciar o awesome, e é
usado pelo widget da wibar (scroll, 5%) e pelas teclas `XF86MonBrightnessUp/Down`
e `Super+Shift+G/F` (2%):

| Backend     | Quando                                         | Como                                  |
| ----------- | ---------------------------------------------- | ------------------------------------- |
| `backlight` | existe `/sys/class/backlight/*` (notebook)     | `brightnessctl`, lido a cada 2 s      |
| `ddc`       | senão, `ddcutil detect` acha um monitor        | `ddcutil --bus N getvcp/setvcp 10`, lido a cada 30 s (cada leitura passa pelo I2C do monitor) |
| `none`      | nenhum dos dois                                | widget escondido, teclas sem efeito   |

O DDC/CI é lento (~100-300 ms por comando) e o monitor recusa comandos
sobrepostos: as chamadas rodam uma de cada vez, e vários passos seguidos de
scroll ou tecla viram uma única escrita do último valor. O widget mostra o
valor novo na hora. Instalação do `ddcutil` e do `i2c-dev`: `setup/hardware.sh`
(ver `../setup/README.md`).

Conferir o backend detectado:

```
awesome-client 'local b = require("config.brightness") return b.backend, b.get()'
```
