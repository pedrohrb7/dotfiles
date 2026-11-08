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

# Pacote do driver NVIDIA. A série já instalada vale (trocar de série é decisão
# manual). Sem nenhuma, escolhe pelo device ID da placa: o "nvidia" atual só
# suporta Turing (GTX 16xx/RTX) em diante; Maxwell, Pascal (ex.: GTX 1050 do
# Acer Nitro) e Volta ficam no nvidia580. Kepler e anteriores (IDs abaixo de
# 0x1340, onde Fermi e Kepler se misturam) não são escolhidos sozinhos.
NVIDIA_SERIES="nvidia nvidia580 nvidia470 nvidia390"
nvidia_pkg() {
	for pkg in $NVIDIA_SERIES; do
		installed "$pkg" && echo "$pkg" && return 0
	done
	addr=$(gpu_devices | awk '$1 == "0x10de" { print $2; exit }')
	id=$(($(cat "/sys/bus/pci/devices/$addr/device")))
	if [ "$id" -ge $((0x1e00)) ]; then
		echo nvidia
	elif [ "$id" -ge $((0x1340)) ]; then
		echo nvidia580
	else
		return 1
	fi
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
if [ $NVIDIA = 1 ]; then
	if ! NVIDIA_PKG=$(nvidia_pkg); then
		echo "Placa NVIDIA antiga (Kepler ou anterior): instale nvidia470 ou nvidia390 à mão e rode de novo." >&2
		exit 1
	fi
	PKGS="$PKGS $NVIDIA_PKG $NVIDIA_PKG-libs-32bit"
fi

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

# O driver NVIDIA (e o -libs-32bit) e o intel-ucode vêm dos repositórios nonfree.
NONFREE=""
case " $MISSING " in *" ${NVIDIA_PKG:-nvidia} "* | *" intel-ucode "*) installed void-repo-nonfree || NONFREE="void-repo-nonfree" ;; esac
case " $MISSING " in *"-libs-32bit "*) installed void-repo-multilib-nonfree || NONFREE="$NONFREE void-repo-multilib void-repo-multilib-nonfree" ;; esac

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

NVIDIA_CONF=10-nvidia-drm-outputclass.conf
# Confs que põem a NVIDIA como GPU principal (instalados por versões antigas
# deste script ou pelo optimus-manager). Viram .bak: o modo usado é o PRIME
# offload, ver setup/README.md.
NVIDIA_PRIMARY_CONFS="10-optimus-manager.conf"
backup() {
	[ -e "$XORG_DIR/$1" ] && as_root mv "$XORG_DIR/$1" "$XORG_DIR/$1.bak"
	true
}
if [ $NVIDIA = 1 ]; then
	# PRIME offload: a Intel (modesetting) desenha a tela e a NVIDIA roda só o
	# que pedir (__NV_PRIME_RENDER_OFFLOAD=1). Num desktop só com a NVIDIA ela é
	# a única GPU, e o mesmo conf serve.
	cmp -s "$DOTFILES/xorg_config/$NVIDIA_CONF" "$XORG_DIR/$NVIDIA_CONF" ||
		as_root install -m644 "$DOTFILES/xorg_config/$NVIDIA_CONF" "$XORG_DIR/"
	for conf in $NVIDIA_PRIMARY_CONFS; do backup "$conf"; done
else
	# Confs da NVIDIA sem a placa impedem o X de iniciar.
	for conf in $NVIDIA_CONF $NVIDIA_PRIMARY_CONFS; do backup "$conf"; done
	echo "  sem NVIDIA: o Xorg usa o modesetting sozinho, nenhum conf de vídeo necessário"
fi

# Teclado us,br como padrão do servidor X (ver awesome/README.md). Um
# 00-keyboard.conf diferente (ex.: gerado pelo systemd-localed) vira .bak.
KEYBOARD="$XORG_DIR/00-keyboard.conf"
if ! cmp -s "$DOTFILES/xorg_config/keyboard.conf" "$KEYBOARD"; then
	[ -e "$KEYBOARD" ] && as_root mv "$KEYBOARD" "$KEYBOARD.bak"
	as_root install -m644 "$DOTFILES/xorg_config/keyboard.conf" "$KEYBOARD"
fi

if has_touchpad && ! cmp -s "$DOTFILES/xorg_config/70-touchpad-settings.conf" "$XORG_DIR/70-touchpad-settings.conf"; then
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
