# setup

Prepara uma instalação nova do Void Linux para estes dotfiles. O mesmo repo
roda no Acer Nitro (Intel + NVIDIA, notebook) e no Dell OptiPlex 3060 Micro
(só Intel UHD 630, desktop): nada é configurado por máquina. O script detecta o
hardware na instalação, e o awesome e o conky detectam o resto toda vez que
iniciam.

```sh
~/dotfiles/setup/hardware.sh -n   # mostra o que faria, sem mexer em nada
~/dotfiles/setup/hardware.sh      # instala (pede a senha do sudo e confirmação do xbps)
```

Pode rodar de novo quando quiser: só instala o que falta. Depois, reinicie a
sessão. Se instalou driver ou microcódigo, reinicie o computador.

## O que o script faz

| Detectado                   | Ação                                                                 |
| --------------------------- | -------------------------------------------------------------------- |
| sempre                      | programas que o awesome e o conky chamam (`pamixer`, `jq`, `blueman`, `rofi`, `flameshot`, `autorandr`...), `mesa-dri`, `vulkan-loader` e as ferramentas de diagnóstico `glxinfo` (`mesa-demos`), `vulkaninfo` (`Vulkan-Tools`) e `vainfo` (`libva-utils`) |
| GPU Intel                   | `mesa-vulkan-intel` (Vulkan), `intel-media-driver` (VA-API: vídeo por hardware no navegador/mpv), `intel-gpu-tools` (`intel_gpu_top`) |
| GPU NVIDIA                  | driver (`<série>` e `<série>-libs-32bit`, ver [NVIDIA](#nvidia-prime-offload)) e `xorg_config/10-nvidia-drm-outputclass.conf` em `/etc/X11/xorg.conf.d/`; um `10-optimus-manager.conf` (NVIDIA como principal) vira `.bak` |
| sem NVIDIA                  | renomeia para `.bak` os confs da NVIDIA que estiverem em `/etc/X11/xorg.conf.d/`: sem a placa, o X não inicia com eles |
| GPU AMD                     | `mesa-vulkan-radeon`, `mesa-vaapi`                                   |
| CPU Intel                   | `intel-ucode` e gera o initramfs de novo (`xbps-reconfigure -f linuxX.Y`) |
| backlight (notebook)        | `brightnessctl`                                                      |
| sem backlight (desktop)     | `ddcutil`, carrega o `i2c-dev` e confere se o monitor responde ao DDC/CI |
| sempre                      | `xorg_config/keyboard.conf` como `/etc/X11/xorg.conf.d/00-keyboard.conf` (layouts `us,br`); um `00-keyboard.conf` diferente que já exista vira `.bak` |
| touchpad                    | `xorg_config/70-touchpad-settings.conf` (tap para clicar)            |

Os pacotes da NVIDIA e o `intel-ucode` vêm dos repositórios nonfree; o script
instala `void-repo-nonfree` (e o multilib, para o `-libs-32bit`) antes.

## NVIDIA (PRIME offload)

Num notebook híbrido (Acer Nitro: Intel + GTX 1050) a Intel desenha a tela e
a NVIDIA fica disponível sob demanda: o `10-nvidia-drm-outputclass.conf` não
tem `PrimaryGPU`, e a NVIDIA aparece como provider `NVIDIA-G0`. Para rodar um
programa nela:

```sh
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia programa
xrandr --listproviders   # modesetting + NVIDIA-G0
```

Série do driver:

| Situação                                  | Pacote      |
| ----------------------------------------- | ----------- |
| já existe uma série instalada (`nvidia`, `nvidia580`, `nvidia470`, `nvidia390`) | mantém essa: trocar de série é decisão manual |
| Turing em diante (GTX 16xx, RTX; device ID >= `0x1e00`) | `nvidia`    |
| Maxwell, Pascal (GTX 1050 do Acer), Volta | `nvidia580` (o `nvidia` atual não suporta mais) |
| Kepler e anteriores                       | o script para e pede para instalar `nvidia470`/`nvidia390` à mão |

Device ID: `cat /sys/bus/pci/devices/0000:01:00.0/device` (ou `lspci -nn`).

Na Intel o Xorg usa o driver `modesetting` embutido (glamor + DRI3), que é o
recomendado. Não instale o `xf86-video-intel`: é legado e pior nas gerações
atuais. A linha `(EE) Failed to load module "intel"` no `Xorg.0.log` é só o
Xorg tentando esse driver antes de cair no modesetting, e não é erro.

## VSCode

O `vscode` do repositório do Void é um build próprio, sem o marketplace da
Microsoft. Aqui usamos o tarball oficial em `/opt/vscode`, que o `.zshrc` já
põe no PATH (`/opt/vscode/bin/code`).

```sh
~/dotfiles/setup/vscode.sh -n   # mostra o que faria
~/dotfiles/setup/vscode.sh      # instala ou atualiza (pede a senha do sudo)
```

O tarball não se atualiza sozinho: para atualizar, rode o script de novo. Ele
compara a versão instalada com a última da API de update da Microsoft, confere
o sha256 do download e troca o `/opt/vscode` inteiro de uma vez. Também cria
`~/.local/share/applications/code.desktop` (menu/rofi) e
`code-url-handler.desktop`, registrado para links `vscode://` (login do GitHub
e da Microsoft pelas extensões). As configurações e extensões ficam em
`~/.config/Code` e `~/.vscode`, fora do `/opt`, então sobrevivem à troca.

As dependências (`nss`, `gtk+3`, `alsa-lib`, `libsecret`, `libxkbfile`,
`xdg-utils`) já vêm com o sistema base deste setup.

## O que se adapta sozinho em cada sessão

| Onde                                   | Como                                                              |
| -------------------------------------- | ----------------------------------------------------------------- |
| `conky/gpu.lua`                        | NVIDIA via `nvidia-smi` se ele responder; senão iGPU Intel pelo sysfs do i915/xe |
| `conky/system.lua`                     | discos, pontos de montagem, interfaces de rede e bateria (a seção some sem bateria) |
| `awesome/config/brightness.lua`        | brilho pelo backlight (`brightnessctl`) ou pelo DDC/CI do monitor (`ddcutil`); sem nenhum dos dois o widget fica escondido |
| `awesome/config/battery.lua`           | sem bateria não faz nada                                          |
| `autorandr/` (`~/.config/autorandr`)   | layout de monitores: aplica o perfil salvo que bate com os monitores conectados (pelo EDID), no login e a cada vez que um monitor é conectado/desconectado. Ver [Monitores](#monitores-autorandr) |
| `awesome/config/autostart.lua`         | inicia o PipeWire quando o socket não existe (`artix-pipewire-launcher` no Artix, `pipewire` no Void) |
| `.zshrc` (`startemulator`)             | emulador Android com PRIME offload na NVIDIA só se o driver estiver carregado |

## Celular como webcam e microfone (scrcpy)

`setup/celular-webcam.sh` usa o celular Android (USB) como webcam e microfone:
a câmera vira a câmera virtual "Celular" (`/dev/video10`, `v4l2loopback`) e o
microfone vira a entrada "Microfone do celular" do PipeWire. Substitui o
antigo `setup/webcam-ampla.sh` (webcam USB DV20, que não é mais usada); o
script remove sozinho o serviço runit `webcam-ampla` que tenha sobrado.

```sh
~/dotfiles/setup/celular-webcam.sh -n   # mostra o que faria
~/dotfiles/setup/celular-webcam.sh      # instala (pede sudo)
~/dotfiles/setup/celular-webcam.sh -r   # remove (mantém scrcpy e android-tools)
```

O que ele instala:

- pacotes `scrcpy`, `android-tools` e `v4l2loopback`;
- regra udev `/etc/udev/rules.d/70-android-adb.rules`;
- `v4l2loopback` em `/dev/video10`, nome "Celular", com `exclusive_caps=1`
  (sem isso Chrome/Vivaldi/Meet não listam a câmera);
- `/etc/pipewire/pipewire.conf.d/30-celular-mic.conf`: sink
  `celular_mic_entrada` e fonte "Microfone do celular" (`celular_mic`, mono);
- `/etc/pipewire/pipewire-pulse.conf.d/30-navegador-volume-mic.conf`: quirk
  `block-source-volume` do `pipewire-pulse` para `vivaldi-bin`, `chrome` e
  `chromium`. O controle automático de ganho do WebRTC (Meet etc.) baixa o
  volume de entrada do sistema durante a chamada (o "Microfone do celular"
  chegou a 55%); o quirk ignora esses pedidos em todos os microfones, e o ganho
  digital do próprio WebRTC continua valendo. O `-r` remove o arquivo;
- o comando `/usr/local/bin/celular-cam`.

Quando o microfone virtual já existe, a instalação também volta o volume do
`celular_mic` para 100%.

O PipeWire só lê a conf ao iniciar, então o microfone virtual aparece depois de
reiniciar a sessão (ou só o PipeWire: `pkill -x pipewire; setsid -f pipewire`,
que traz de volta o wireplumber e o pipewire-pulse pelo `pipewire.conf.d`).
Mudanças no PipeWire, como a do volume acima, valem do mesmo jeito; reabra o
navegador depois, porque um navegador aberto durante o restart perde a conexão
de áudio. O `celular-cam` não roda sem ele, nem sem o celular no adb.

No celular: Opções do desenvolvedor > Depuração USB ligada, e aceitar a chave
do computador. Precisa de Android 12+ para a câmera e 11+ para o microfone.
O Android revoga a autorização do adb após 7 dias sem conectar, a menos que
"Desativar tempo limite de autorização adb" esteja ligado nas opções do
desenvolvedor.

```sh
celular-cam                        # câmera frontal 1280x720, 30 fps
celular-cam --camera-facing=back   # argumentos extras vão para o scrcpy
scrcpy --list-cameras --list-camera-sizes   # câmeras e resoluções do aparelho
```

O `celular-cam` manda a câmera para `/dev/video10` e o microfone do celular
para o microfone virtual, sem janela; Ctrl+C para. No Meet: câmera "Celular",
microfone "Microfone do celular".

Fluxo do dia a dia: conecte o celular, rode `celular-cam` ANTES de escolher a
câmera no Meet (por causa do `exclusive_caps`, "Celular" só aparece na lista
enquanto o `celular-cam` roda) e use Ctrl+C para encerrar.

Armadilhas já resolvidas (testado num Xiaomi 11 Lite 5G NE, Android 14,
scrcpy 5.0.1):

- Sem a regra udev, com o celular em "só carregar"/só ADB, o `adb` diz "no
  permissions": as regras do sistema só liberam o acesso pela interface MTP.
- O scrcpy ignora `PULSE_SINK` e toca sempre na saída padrão (a voz saía no
  alto-falante). O `celular-cam` usa `SDL_AUDIODRIVER=pipewire` e
  `PIPEWIRE_PROPS='{ target.object = "celular_mic_entrada" }'` para ligar o
  stream direto ao microfone virtual.
- `scrcpy --stay-awake` falha no Xiaomi ("Could not change
  stay_on_while_plugged_in") a menos que "Depuração USB (configurações de
  segurança)" esteja ligada; por isso não é usado.

## ThinkPad T440p (ABNT2): tecla "/ ?"

No T440p com teclado ABNT2, a tecla "/ ?" fica ao lado do PrtSc, na posição do
Ctrl direito, e manda o scancode dele (`0x9d`, lido como `KEY_RIGHTCTRL`, keycode
97). Por isso ela não digitava nada. O XKB já estava certo: o grupo `br` mapeia
a `<AB11>` para `/`, `?`, `°` e `¿`. Falta só o kernel entregar a tecla certa.

`setup/thinkpad-t440p-br.sh` instala a regra udev hwdb
`/etc/udev/hwdb.d/61-keyboard-thinkpad-t440p-br.hwdb`, que casa com
`evdev:atkbd:dmi:...:pvrThinkPadT440p:*` e remapeia `KEYBOARD_KEY_9d=ro`
(`KEY_RO`, a "/ ?" do ABNT2, que o X vê como keycode 97 `<AB11>`). Depois roda
`udevadm hwdb --update` e `udevadm trigger --subsystem-match=input
--action=change`, então não precisa reiniciar. Vale no TTY e no X.

O script é separado do `hardware.sh` de propósito: o problema só existe nesse
ThinkPad e o `hardware.sh` roda em outras máquinas. Em qualquer máquina cujo
`/sys/class/dmi/id/product_version` não seja `ThinkPad T440p`, ele sai com erro
sem alterar nada.

```sh
~/dotfiles/setup/thinkpad-t440p-br.sh -n   # mostra o que faria
~/dotfiles/setup/thinkpad-t440p-br.sh      # instala (pede sudo); pode repetir
~/dotfiles/setup/thinkpad-t440p-br.sh -r   # remove a regra
```

Só uma opção é lida por vez. Conferir:

```sh
udevadm info /dev/input/event0 | grep KEYBOARD_KEY   # KEYBOARD_KEY_9d=ro
```

A tecla deve dar `/` e `?`, e com AltGr, `°`.

Efeitos: o Ctrl direito deixa de existir (é o mesmo scancode); o esquerdo não
muda. No grupo de layout `us` a tecla não digita nada, porque o `us` não tem
`<AB11>`.

## Conferir a aceleração

```sh
glxinfo -B | grep -E 'renderer|Accelerated'   # Mesa Intel(R) UHD Graphics 630 / yes
vulkaninfo --summary | grep deviceName
vainfo | grep -E 'Driver version|VAProfileH264'   # iHD
sudo intel_gpu_top                              # uso da iGPU por engine
```

## Monitores (autorandr)

`~/.config/autorandr` é um symlink para `~/dotfiles/autorandr`
(`ln -s ~/dotfiles/autorandr ~/.config/autorandr`). Cada perfil é uma pasta
com `setup` (o EDID de cada monitor, que identifica a combinação) e `config`
(modo, posição e monitor principal de cada saída).

- **Quando roda:** no login (`awesome/config/autostart.lua`) e, ao conectar ou
  desconectar um monitor, pela regra udev do pacote
  (`/usr/lib/udev/rules.d/40-monitor-hotplug.rules`), que chama
  `autorandr --batch --change --default default` na sessão X do usuário. Não
  depende de systemd.
- **Combinação sem perfil:** `default` é um symlink para o perfil virtual
  `horizontal`, que liga todos os monitores conectados lado a lado. Depois
  dele, o hook `autorandr/horizontal/postswitch` põe o monitor principal à
  esquerda e os outros à direita (o `horizontal` sozinho segue a ordem do
  xrandr, e um monitor no HDMI-1 ficaria à esquerda do DP-1).
- **Perfis salvos (Dell OptiPlex):** `optiplex` (só o monitor do DP-1 em
  1920x1080) e `optiplex-dual` (DP-1 principal à esquerda + o monitor do
  HDMI-1 à direita, ambos em 1920x1080).

Salvar uma combinação nova (ex.: um segundo monitor): conecte, ajuste no
`arandr` (posição, resolução, principal) e rode

```sh
autorandr --save nome      # cria ~/dotfiles/autorandr/nome
autorandr                  # lista os perfis; o atual aparece como (current)
autorandr --change         # aplica na mão o perfil que bate
```

O `~/.screenlayout/screen.sh` do arandr não é mais usado no login.

## Brilho do monitor (DDC/CI)

No desktop não existe `/sys/class/backlight`; o brilho é o do próprio monitor,
mudado pelo cabo (HDMI/DP) com DDC/CI. O monitor precisa ter a opção DDC/CI
ligada no menu dele. Conferir:

```sh
ddcutil detect           # deve listar o monitor com "I2C bus: /dev/i2c-N"
ddcutil getvcp 10        # brilho atual
```

O pacote `ddcutil` traz `/usr/lib/modules-load.d/ddcutil.conf` (carrega o
`i2c-dev` no boot) e a regra udev `60-ddcutil-i2c.rules`, que dá acesso ao
`/dev/i2c-*` do monitor para o usuário logado. Não precisa de grupo `i2c`.
