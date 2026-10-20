# conky

Painel de sistema fixo no desktop, coluna à direita abaixo da wibar do awesome.
Template próprio (`conky.conf`, sintaxe Lua do conky 1.10+), com a paleta Tokyo
Night de `awesome/config/styles/color.lua`.

Seções: sistema, CPU (gráfico, frequência, temperatura, uso por núcleo), memória,
disco (`/`, `/mnt/data`, I/O e temperatura do NVMe), rede (Wi-Fi, Ethernet e VPN,
cada uma só aparece quando tem IP), Bluetooth (um bloco por adaptador, dongle
USB e interno, com os dispositivos conectados e a bateria de cada um quando o
dispositivo informa), top 3 processos por CPU e top 3 por memória, e bateria.

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

Restrições: as seções abaixo do Bluetooth não podem ter gráficos (`*graph`
deixa a linha mais alta que `LINE_HEIGHT`). Ao trocar a fonte, ajustar
`LINE_HEIGHT` em `click.lua`.

Dependências: `bluez`, `jq`, `blueman`.

Valores específicos desta máquina (trocar em outra): interfaces `wlp2s0`,
`enp3s0f1`, `tun0`; disco `nvme0n1`; ponto de montagem `/mnt/data`; bateria
`BAT1`; sensores `hwmon coretemp` e `hwmon nvme`. Limites de alerta (vermelho):
disco `/` >= 90%, bateria <= 20%.
