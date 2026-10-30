#!/bin/sh
# Prepara uma instalação do Void Linux para estes dotfiles, de acordo com o
# hardware detectado: drivers de vídeo (Intel, NVIDIA, AMD), microcódigo da
# CPU, confs do Xorg, controle de brilho (backlight do notebook ou DDC/CI do
# monitor) e os programas que o awesome e o conky chamam.
# Pode rodar quantas vezes quiser: só instala o que falta. Ver setup/README.md.
#
# Uso: setup/hardware.sh [-n]
#   -n  só mostra o que seria feito, sem instalar nem alterar nada
set -eu

DOTFILES=$(cd "$(dirname "$0")/.." && pwd)
XORG_DIR=/etc/X11/xorg.conf.d
DRY=0

case "${1:-}" in
-n) DRY=1 ;;
"") ;;
*)
	sed -n '2,10s/^# \{0,1\}//p' "$0"
	exit 2
	;;
esac

say() { printf '\033[1;35m==>\033[0m %s\n' "$*"; }
run() {
	printf '  + %s\n' "$*"
	[ "$DRY" = 1 ] || "$@"
}
as_root() {
	if [ "$(id -u)" = 0 ]; then run "$@"; else run sudo "$@"; fi
}
installed() { xbps-query "$1" > /dev/null 2>&1; }

# Detecção -------------------------------------------------------------------

# Vendor de cada placa de vídeo PCI (classe 0x03xxxx): 0x8086 Intel,
# 0x10de NVIDIA, 0x1002 AMD.
gpu_devices() {
	for dev in /sys/bus/pci/devices/*; do
		case "$(cat "$dev/class")" in
		0x03*) echo "$(cat "$dev/vendor") ${dev##*/}" ;;
		esac
	done
}

has_gpu() { gpu_devices | grep -q "^$1 "; }

# 0000:01:00.0 (hex) -> PCI:1:0:0 (decimal), formato do BusID do Xorg.
busid() {
	addr=$(gpu_devices | awk -v v="$1" '$1 == v { print $2; exit }')
	[ -n "$addr" ] || return 1
	bdf=${addr#*:} # 01:00.0
	printf 'PCI:%d:%d:%d\n' "0x${bdf%%:*}" "0x$(echo "$bdf" | cut -d: -f2 | cut -d. -f1)" "0x${bdf##*.}"
}

# Bateria do próprio computador (scope "Device" é de periférico Bluetooth).
has_battery() {
	for ps in /sys/class/power_supply/*; do
		[ -r "$ps/type" ] || continue
		[ "$(cat "$ps/type")" = Battery ] || continue
		[ "$(cat "$ps/scope" 2> /dev/null)" = Device ] || return 0
	done
	return 1
}

has_backlight() { [ -n "$(ls -A /sys/class/backlight 2> /dev/null)" ]; }
has_touchpad() { grep -qi touchpad /proc/bus/input/devices 2> /dev/null; }
cpu_vendor() { awk -F': ' '/^vendor_id/ { print $2; exit }' /proc/cpuinfo; }

INTEL=0 NVIDIA=0 AMD=0
has_gpu 0x8086 && INTEL=1
has_gpu 0x10de && NVIDIA=1
has_gpu 0x1002 && AMD=1

say "Hardware detectado"
printf '  GPU:        %s\n' "$( {
	[ $INTEL = 1 ] && echo Intel
	[ $NVIDIA = 1 ] && echo NVIDIA
	[ $AMD = 1 ] && echo AMD
	true
} | paste -sd' ')"
printf '  CPU:        %s\n' "$(cpu_vendor)"
printf '  Bateria:    %s\n' "$(has_battery && echo sim || echo não)"
printf '  Backlight:  %s\n' "$(has_backlight && echo sim || echo 'não (brilho do monitor via DDC/CI)')"
printf '  Touchpad:   %s\n' "$(has_touchpad && echo sim || echo não)"

# Pacotes --------------------------------------------------------------------

# Chamados pelo awesome (autostart, widgets, atalhos) e pelo conky.
PKGS="awesome kitty picom conky jq bluez blueman pamixer pavucontrol rofi flameshot pciutils autorandr"
# Ferramentas para conferir a aceleração: glxinfo, vulkaninfo, vainfo.
PKGS="$PKGS mesa-dri vulkan-loader mesa-demos Vulkan-Tools libva-utils"

# Intel: Vulkan (ANV), VA-API (iHD, Broadwell em diante) e intel_gpu_top.
# O driver do Xorg fica o modesetting embutido: o xf86-video-intel é legado.
[ $INTEL = 1 ] && PKGS="$PKGS mesa-vulkan-intel intel-media-driver intel-gpu-tools"
[ $AMD = 1 ] && PKGS="$PKGS mesa-vulkan-radeon mesa-vaapi"
[ $NVIDIA = 1 ] && PKGS="$PKGS nvidia nvidia-libs-32bit"

case "$(cpu_vendor)" in
GenuineIntel) PKGS="$PKGS intel-ucode" ;;
esac

if has_backlight; then
	PKGS="$PKGS brightnessctl"
else
	PKGS="$PKGS ddcutil"
fi

MISSING=""
for pkg in $PKGS; do
	installed "$pkg" || MISSING="$MISSING $pkg"
done

# nvidia, nvidia-libs-32bit e intel-ucode vêm dos repositórios nonfree.
NONFREE=""
case " $MISSING " in *" nvidia "* | *" intel-ucode "*) installed void-repo-nonfree || NONFREE="void-repo-nonfree" ;; esac
case " $MISSING " in *" nvidia-libs-32bit "*) installed void-repo-multilib-nonfree || NONFREE="$NONFREE void-repo-multilib void-repo-multilib-nonfree" ;; esac

say "Pacotes"
if [ -n "$NONFREE" ]; then
	# shellcheck disable=SC2086
	as_root xbps-install -S $NONFREE
fi
if [ -n "$MISSING" ]; then
	# shellcheck disable=SC2086
	as_root xbps-install -S $MISSING
else
	echo "  todos já instalados"
fi

# O microcódigo entra no initramfs: precisa gerar de novo depois de instalar.
case " $MISSING " in
*" intel-ucode "*) as_root xbps-reconfigure -f "linux$(uname -r | cut -d. -f1,2)" ;;
esac

# Xorg -----------------------------------------------------------------------

say "Xorg ($XORG_DIR)"
as_root mkdir -p "$XORG_DIR"

NVIDIA_CONFS="10-nvidia-drm-outputclass.conf 10-optimus-manager.conf"
if [ $NVIDIA = 1 ]; then
	as_root install -m644 "$DOTFILES/xorg_config/10-nvidia-drm-outputclass.conf" "$XORG_DIR/"
	# BusID do conf é o do Acer Nitro; usa os endereços desta máquina.
	tmp=$(mktemp)
	sed -e "/Identifier \"nvidia\"/,/EndSection/s/BusID \".*\"/BusID \"$(busid 0x10de)\"/" \
		-e "/Identifier \"integrated\"/,/EndSection/s/BusID \".*\"/BusID \"$(busid 0x8086 || echo PCI:0:2:0)\"/" \
		"$DOTFILES/xorg_config/10-optimus-manager.conf" > "$tmp"
	as_root install -m644 "$tmp" "$XORG_DIR/10-optimus-manager.conf"
	rm -f "$tmp"
else
	# Confs da NVIDIA sem a placa impedem o X de iniciar.
	for conf in $NVIDIA_CONFS; do
		[ -e "$XORG_DIR/$conf" ] && as_root mv "$XORG_DIR/$conf" "$XORG_DIR/$conf.bak"
	done
	echo "  sem NVIDIA: o Xorg usa o modesetting sozinho, nenhum conf de vídeo necessário"
fi

# Teclado us,br como padrão do servidor X (ver awesome/README.md). Um
# 00-keyboard.conf diferente (ex.: gerado pelo systemd-localed) vira .bak.
KEYBOARD="$XORG_DIR/00-keyboard.conf"
if ! cmp -s "$DOTFILES/xorg_config/keyboard.conf" "$KEYBOARD"; then
	[ -e "$KEYBOARD" ] && as_root mv "$KEYBOARD" "$KEYBOARD.bak"
	as_root install -m644 "$DOTFILES/xorg_config/keyboard.conf" "$KEYBOARD"
fi

if has_touchpad; then
	as_root install -m644 "$DOTFILES/xorg_config/70-touchpad-settings.conf" "$XORG_DIR/"
fi

# Brilho ---------------------------------------------------------------------

if ! has_backlight; then
	# O pacote ddcutil traz o modules-load.d do i2c-dev e a regra udev que dá
	# acesso ao /dev/i2c-* do monitor para quem está logado (uaccess).
	say "Brilho do monitor (DDC/CI)"
	as_root modprobe i2c-dev
	as_root udevadm trigger --subsystem-match=i2c-dev
	if [ "$DRY" = 0 ] && command -v ddcutil > /dev/null; then
		sleep 1
		if ddcutil detect --terse 2> /dev/null | grep -q '/dev/i2c-'; then
			echo "  monitor com DDC/CI encontrado"
		else
			echo "  nenhum monitor respondeu ao DDC/CI: ative DDC/CI no menu do monitor"
		fi
	fi
fi

say "Pronto. Reinicie a sessão (ou o computador, se instalou driver ou microcódigo)."
