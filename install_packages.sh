#!/bin/bash

if ["$(id -u)" -ne 0 ]; then
    echo "Must run as root"
    exit 1
fi

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
  "rofi"
  "archlinux-keyring"
  "picom"
)

aur_packages=(
  "fzf-git"
)

install_pacman_packages() {
  echo "Sync and Update system..."
  pacman -Syu --noconfirm

  echo "Installing PACMAN packages..."
  for package in "${pacman_packages[@]}"; do
    pacman -S --noconfirm "$package"
  done
}

install_aur_packages() {
  echo "Installing AUR packages..."
  for package in "${aur_packages[@]}"; do
    yay -S --noconfirm "$package"
  done
}

install_pacman_packages()
install_aur_packages()

echo "All packages installed with sucess... Logout and login again!"
