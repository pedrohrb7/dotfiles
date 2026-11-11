# Terminator

`~/.config/terminator` é um symlink para esta pasta, então `config` e
`plugins/` já são rastreados pelo git.

```sh
ln -s ~/dotfiles/terminator ~/.config/terminator
```

## Abas (`tabs.css`)

O Terminator não tem opção de altura/cor das abas no `config`; o visual vem do
GTK CSS. `tabs.css` deixa as abas compactas (~19px) no tema Catppuccin Mocha
(barra `mantle`, aba ativa `base` com faixa `mauve`), tudo escopado em
`.terminator-terminal-window` para não afetar outros apps GTK.

Ele é carregado pelo CSS de usuário do GTK3, que também está no repo:

```
~/.config/gtk-3.0/gtk.css -> ~/dotfiles/awesome/gtk-3.0/gtk.css
                              @import url("../terminator/tabs.css")
```

O `@import` é relativo a `~/.config/gtk-3.0`, então resolve para
`~/.config/terminator/tabs.css` (o symlink desta pasta). Em máquina nova:

```sh
ln -s ~/dotfiles/awesome/gtk-3.0/gtk.css ~/.config/gtk-3.0/gtk.css
```

O CSS de usuário tem prioridade sobre o CSS que o Terminator injeta, então os
ajustes sempre vencem. Mudanças valem para janelas novas do Terminator; feche
todas (o processo é único) para recarregar.

Ajustes rápidos:

- altura: `padding` de `tab` (vertical) e `font-size`
- cores: os `@define-color` no topo do arquivo
- posição da faixa: `tab_position` no `config` (`bottom` usa faixa em cima da
  aba; `top` usa faixa embaixo)
