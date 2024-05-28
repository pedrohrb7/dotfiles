#!/bin/bash

# validate if its running with root
if ["$(id -u)" -ne 0 ]; then
    echo "Must run as root"
    exit 1
fi

# validate if yay or paru is installed
if [! command -v yay &> /dev/null]; then
    echo "yay not installed..."
else 
    echo "installing yay..."   
    git clone https://aur.archlinux.org/yay.git
    cd yay || exit
    makepkg -si --noconfirm
    cd ..
    rm -rf yay
    echo "yay installed..."
fi

# Lista de pacotes a serem instalados com pacman
pacman_packages=(
  "neovim"
  "htop"
  "curl"
  "wget"
  "neofetch"
  "gcc"
  "make"
  "fd"
  "ripgrep"
  "bat"
  "eza"
  "kitty"
  "zsh"
  "xclip"
  "fzf"
  "polybar"
  "rofi"
  "conky"
  "archlinux-keyring"
  "picom"
)

# Lista de pacotes a serem instalados com yay
aur_packages=(
  "fzf-git"
  "arcolinux-logout"
  "qtile-exras"
)

# install pacman packages
install_pacman_packages() {
  echo "Sync and Update system..."
  pacman -Syu --noconfirm

  echo "Installing PACMAN packages..."
  for package in "${pacman_packages[@]}"; do
    pacman -S --noconfirm "$package"
  done
}

# install aur packages
install_aur_packages() {
  echo "Installing AUR packages..."
  for package in "${aur_packages[@]}"; do
    yay -S --noconfirm "$package"
  done
}

install_pacman_packages()
install_aur_packages()

echo "All packages installed with sucess... Logout and login again!"
