#!/bin/sh
# Tecla "/ ?" do ThinkPad T440p com teclado ABNT2. Ela fica ao lado do PrtSc,
# no lugar do Ctrl direito, e manda o mesmo scancode dele (0x9d): o kernel a lê
# como KEY_RIGHTCTRL e ela não digita nada. Uma regra do udev hwdb a remapeia
# para KEY_RO, a "/ ?" do ABNT2, que o layout br já mapeia (vale no TTY e no X).
# O Ctrl direito deixa de existir; o esquerdo continua. Ver setup/README.md.
#
# Uso: setup/thinkpad-t440p-br.sh [-n | -r]
#   -n  só mostra o que seria feito, sem instalar nem alterar nada
#   -r  remove a regra e volta a tecla a ser o Ctrl direito
set -eu

MODEL=ThinkPadT440p
HWDB=/etc/udev/hwdb.d/61-keyboard-thinkpad-t440p-br.hwdb
DRY=0
MODE=install

case "${1:-}" in
-n) DRY=1 ;;
-r) MODE=remove ;;
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

# write_root <destino> <modo>: grava o stdin no destino como root, só se mudou.
write_root() {
	tmp=$(mktemp)
	cat > "$tmp"
	if [ -e "$1" ] && cmp -s "$tmp" "$1"; then
		echo "  = $1 já está atualizado"
		rm -f "$tmp"
		return 1
	fi
	as_root install -D -m "$2" "$tmp" "$1"
	rm -f "$tmp"
}

# Recompila o hwdb e reaplica os keymaps nos teclados, sem reiniciar.
reload() {
	as_root udevadm hwdb --update
	as_root udevadm trigger --subsystem-match=input --action=change
}

if [ "$MODE" = remove ]; then
	say "removendo a regra da tecla / ?"
	if [ -e "$HWDB" ]; then
		as_root rm "$HWDB"
		reload
	else
		echo "  = $HWDB não existe"
	fi
	say "pronto"
	exit 0
fi

model=$(cat /sys/class/dmi/id/product_version 2> /dev/null || true)
if [ "$(echo "$model" | tr -d ' ')" != "$MODEL" ]; then
	echo "Este script é só para o ThinkPad T440p (detectado: ${model:-desconhecido})." >&2
	exit 1
fi

say "tecla / ? do teclado ABNT2 ($HWDB)"
if write_root "$HWDB" 0644 << EOF; then
# Gerado por ~/dotfiles/setup/thinkpad-t440p-br.sh. A tecla "/ ?" do T440p
# ABNT2 manda o scancode do Ctrl direito (0x9d); aqui ela vira KEY_RO (<AB11>).
evdev:atkbd:dmi:bvn*:bvr*:bd*:svnLENOVO:pn*:pvr$MODEL:*
 KEYBOARD_KEY_9d=ro
EOF
	reload
fi

say "pronto. No layout br a tecla dá / e ?; com AltGr, °"
