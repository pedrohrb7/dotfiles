## dwm

![DWM screenshot](https://raw.githubusercontent.com/pedrohrb7/dotfiles/refs/heads/main/dwm_screen.png)

## awesomewm

![Awesome screenshot](https://raw.githubusercontent.com/pedrohrb7/dotfiles/refs/heads/main/awesome_screen.png)

## Nova instalação

`setup/hardware.sh` detecta o hardware (GPU Intel/NVIDIA/AMD, notebook ou
desktop) e instala drivers, confs do Xorg e os programas que o awesome e o
conky usam. O resto (GPU no conky, discos, rede, bateria, brilho) se adapta
sozinho a cada sessão. Ver [setup/README.md](setup/README.md).

```sh
~/dotfiles/setup/hardware.sh -n   # o que seria feito
~/dotfiles/setup/hardware.sh
```

## Packages

VoidLinux base system

- Awesome WM
- DWM
- i3
- Vivaldi
- bat (a better cat)
- eza (a better ls)
- FiraCode Nerd Font
- MartianMono Nerd Font
- fzf-git
- kitty (on awesomewm)
- st (on dwm)
- lazygit
- lazydocker
- neovim (smoothvim)
- ripgrep
- pavucontrol
- brightnessctl (notebook) / ddcutil (desktop, brilho do monitor por DDC/CI)
- pamixer
- jq (seção Bluetooth do conky)
- xclip
- xorg-xclipboard
- xorg-xbacklight
- yazi
- conky (painel de sistema no awesome, ver conky/README.md)
- zsh
