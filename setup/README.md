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
| GPU NVIDIA                  | `nvidia`, `nvidia-libs-32bit` e os confs de `xorg_config/` em `/etc/X11/xorg.conf.d/`, com o `BusID` da máquina |
| sem NVIDIA                  | renomeia para `.bak` os confs da NVIDIA que estiverem em `/etc/X11/xorg.conf.d/`: sem a placa, o X não inicia com eles |
| GPU AMD                     | `mesa-vulkan-radeon`, `mesa-vaapi`                                   |
| CPU Intel                   | `intel-ucode` e gera o initramfs de novo (`xbps-reconfigure -f linuxX.Y`) |
| backlight (notebook)        | `brightnessctl`                                                      |
| sem backlight (desktop)     | `ddcutil`, carrega o `i2c-dev` e confere se o monitor responde ao DDC/CI |
| sempre                      | `xorg_config/keyboard.conf` como `/etc/X11/xorg.conf.d/00-keyboard.conf` (layouts `us,br`); um `00-keyboard.conf` diferente que já exista vira `.bak` |
| touchpad                    | `xorg_config/70-touchpad-settings.conf` (tap para clicar)            |

Os pacotes da NVIDIA e o `intel-ucode` vêm dos repositórios nonfree; o script
instala `void-repo-nonfree` (e o multilib, para `nvidia-libs-32bit`) antes.

Na Intel o Xorg usa o driver `modesetting` embutido (glamor + DRI3), que é o
recomendado. Não instale o `xf86-video-intel`: é legado e pior nas gerações
atuais. A linha `(EE) Failed to load module "intel"` no `Xorg.0.log` é só o
Xorg tentando esse driver antes de cair no modesetting, e não é erro.

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
