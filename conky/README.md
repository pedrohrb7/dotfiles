# conky

Painel de sistema fixo no desktop, coluna à direita abaixo da wibar do awesome.
Template próprio (`conky.conf`, sintaxe Lua do conky 1.10+), com a paleta Tokyo
Night de `awesome/config/styles/color.lua`.

Seções: sistema, CPU (gráfico, frequência, temperatura, uso por núcleo), GPU
(NVIDIA ou Intel: modelo, clock, uso com gráfico, temperatura e, na NVIDIA, VRAM),
memória, disco (cada ponto de montagem, I/O e temperatura de cada disco), rede
(Wi-Fi, Ethernet e VPN, cada uma só aparece quando tem IP), Bluetooth (um bloco por adaptador, dongle
USB e interno, com os dispositivos conectados e a bateria de cada um quando o
dispositivo informa), top 3 processos por CPU e top 3 por memória, e bateria
(só em máquina com bateria).

O mesmo `conky.conf` serve em qualquer máquina: o que depende do hardware é
detectado ao rodar (ver [Detecção do hardware](#detecção-do-hardware)).

Clicar na seção Bluetooth abre o `blueman-manager`.

## Instalar

```sh
sudo xbps-install -S conky
ln -s ~/dotfiles/conky ~/.config/conky
```

O awesome inicia o conky sozinho (`awesome/config/autostart.lua`, só se o binário
existir). Para iniciar na mão: `conky --daemonize`.

## Fixo no desktop, não como janela

Dois lados garantem isso:

| Onde                          | O quê                                                                 |
| ----------------------------- | --------------------------------------------------------------------- |
| `conky.conf`                  | `own_window_type = "desktop"` e hints `undecorated,below,sticky,skip_taskbar,skip_pager` |
| `awesome/config/rules.lua`    | regra `class = "Conky"`: `sticky`, `below`, `focusable = false`, sem borda, fora da tasklist, sem placement do awesome |

Resultado: aparece em todas as tags, fica atrás das janelas, não recebe foco e
não aparece na tasklist. Cliques chegam ao conky quando não há janela por cima
(ver [Cliques](#cliques)).

A transparência (`own_window_argb_*`) depende do picom. O autostart usa
`--pause=2` para o picom subir antes.

## Editar

Recarregar: o conky relê o `conky.conf` sozinho ao salvar. Se não, `pkill conky && conky --daemonize`.

Estrutura do arquivo:

- `conky.config`: janela, posição (`alignment`, `gap_x`, `gap_y`, largura), fonte,
  intervalo, paleta (`color0`..`color7`) e templates.
- `conky.text`: o layout. `${colorN}` muda a cor, `${goto X}` vai para a coluna X
  em pixels, `${alignr}` alinha à direita.

Templates (`${templateN arg1 arg2}`, os argumentos substituem `\1`, `\2`; são
separados por espaço, então valores com espaço não podem ser argumento):

| Template    | Uso                                      |
| ----------- | ---------------------------------------- |
| `template0` | cabeçalho de seção: `${template0 <ícone> <TÍTULO>}` |
| `template1` | linha rótulo/valor: `${template1 <rótulo> <valor>}` |
| `template2` | linha do top por CPU: `${template2 <n>}` |
| `template3` | linha do top por memória: `${template3 <n>}` |
| `template4` | bloco de rede: `${template4 <interface>}` |

## GPU

`gpu.lua` escolhe a placa uma vez, ao carregar:

| Backend | Quando                            | De onde vêm os valores |
| ------- | --------------------------------- | ---------------------- |
| NVIDIA  | `nvidia-smi` responde (driver carregado) | `nvidia-smi --query-gpu`: o conky do Void não é compilado com `${nvidia}`. Uma chamada (~20 ms) por atualização serve todos os campos |
| Intel   | senão, se há iGPU Intel com i915 ou xe | sysfs, sem root: clock real (`rps_act_freq_mhz`), uso pela residência RC6 (100% menos a fração do intervalo em que a GPU dormiu), temperatura do pacote da CPU (`coretemp`; a iGPU não tem sensor próprio). Não há VRAM: a memória é a RAM, e as linhas de VRAM somem |

No Acer com o optimus em modo integrado (NVIDIA desligada), a seção mostra a Intel.

| Em `conky.text`             | O quê                                                   |
| --------------------------- | ------------------------------------------------------- |
| `${lua gpu <campo>}`        | `ok` (1/0), `name`, `util`, `temp`, `clock` (MHz), `has_vram` (1/0), `vram`, `vram_perc` |
| `${lua_graph gpu_util ...}` | gráfico do uso da GPU (%)                               |
| `${lua_bar gpu_vram}`       | barra da VRAM usada (%)                                 |

Sem nenhuma das duas, a seção mostra "GPU não detectada".

## Bluetooth e cliques

| Arquivo         | O quê                                                                 |
| --------------- | --------------------------------------------------------------------- |
| `bluetooth.sh`  | gera o texto da seção: lê adaptadores e dispositivos do BlueZ numa chamada D-Bus (`busctl` + `jq`). Adaptador USB removível vira "Dongle", fixo vira "Interno" |
| `bluetooth.lua` | `${lua_parse bluetooth}`: roda o script a cada 5 s e guarda quantas linhas a seção tem (`bluetooth_lines`) |
| `click.lua`     | `lua_mouse_hook`: clique esquerdo na seção Bluetooth abre o `blueman-manager` |

### Cliques

O conky (compilado com "Mouse events", ver `conky -v`) chama `conky_on_mouse`
com as coordenadas relativas à janela. A seção Bluetooth fica logo abaixo da
rede, e a área clicável é calculada a partir do fim da janela: no clique, o
`click.lua` lê o `conky.text`, renderiza com `conky_parse` o trecho depois de
`${lua_parse bluetooth}` e conta as linhas. A seção ocupa `bluetooth_lines` x
`LINE_HEIGHT` (16 px para FiraCode Nerd Font size=9) logo acima dessas linhas.
Assim a conta acompanha as seções que mudam de altura (bateria).

### Bateria dos dispositivos

A bateria vem do `org.bluez.Battery1`. Controles de jogo (DualShock 4 e
clones via `hid-playstation`/`hid-sony`, Switch via `hid-nintendo`) não
reportam ao BlueZ: o driver cria `/sys/class/power_supply/*<mac em
minúsculas>`, e o `bluetooth.sh` lê o `capacity` de lá como fallback.

Controle "conectado" sem bateria e sem funcionar como joystick: o BlueZ
recusa HID clássico de dispositivo sem bond (`ClassicBondedOnly=true`, padrão
em `/etc/bluetooth/input.conf`). Conferir `Bonded: yes` em
`bluetoothctl info <mac>`; se for `no`, remover e parear de novo.

Restrições: as seções abaixo do Bluetooth não podem ter gráficos (`*graph`
deixa a linha mais alta que `LINE_HEIGHT`). Ao trocar a fonte, ajustar
`LINE_HEIGHT` em `click.lua`.

Dependências: `bluez`, `jq`, `blueman`.

## Detecção do hardware

`system.lua` gera as seções que mudam de máquina para máquina, com as
variáveis do conky já apontando para os nomes certos. A detecção roda a cada
10 s (`INTERVAL`), então um pendrive montado ou uma VPN aparecem sozinhos; os
valores em si atualizam a cada `update_interval`.

| Em `conky.text`       | O quê                                                                 |
| --------------------- | --------------------------------------------------------------------- |
| `${lua_parse disks}`  | cada partição montada de `/proc/mounts` (fora `/boot*`, `/efi`, `/var/lib/docker`, `/snap` e binds da mesma partição), e uma linha de I/O por disco com o rótulo `NVMe`, `SSD`, `HDD` ou `USB` (o nome do disco quando dois são do mesmo tipo) e a temperatura se o disco tiver hwmon (`nvme`, ou `drivetemp` para SATA) |
| `${lua_parse network}`| Wi-Fi (`phy80211`), Ethernet (placa física: `docker0`, `veth*`, `br-*` ficam de fora) e VPN (`tun`/`tap`, `wg*`), cada uma dentro de `${if_up}` |
| `${lua_parse battery}`| a seção BATERIA inteira, com a primeira bateria do próprio computador (`BAT0`, `BAT1`...); vazia sem bateria |

Fixos no `conky.conf`: sensor da CPU `hwmon coretemp` e os quatro núcleos
`cpu1`..`cpu4`. Limites de alerta (vermelho): ponto de montagem >= 90%,
bateria <= 20%.
