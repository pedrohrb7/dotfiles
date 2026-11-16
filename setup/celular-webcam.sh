#!/bin/sh
# Celular Android (USB) como webcam e microfone, pelo scrcpy.
# A câmera do celular vira a câmera virtual "Celular" (/dev/video10, via
# v4l2loopback) e o microfone vira a entrada "Microfone do celular" do PipeWire.
# Instala o comando celular-cam, que liga os dois. Pode rodar quantas vezes
# quiser. Ver setup/README.md.
#
# Uso: setup/celular-webcam.sh [-n | -r]
#   -n  só mostra o que seria feito, sem instalar nem alterar nada
#   -r  remove tudo (comando, regra udev, confs do PipeWire e do módulo, pacote v4l2loopback)
#
# Também impede o navegador (Meet e outros sites WebRTC) de mudar o volume dos
# microfones do sistema.
set -eu

VNR=10
LABEL="Celular"
MIC_SINK=celular_mic_entrada
MIC_SOURCE=celular_mic
CMD=/usr/local/bin/celular-cam
UDEV_RULE=/etc/udev/rules.d/70-android-adb.rules
PW_CONF=/etc/pipewire/pipewire.conf.d/30-celular-mic.conf
PULSE_CONF=/etc/pipewire/pipewire-pulse.conf.d/30-navegador-volume-mic.conf
MODPROBE_CONF=/etc/modprobe.d/v4l2loopback.conf
MODLOAD_CONF=/etc/modules-load.d/v4l2loopback.conf
OLD_SV=/etc/sv/webcam-ampla
DRY=0
MODE=install

case "${1:-}" in
-n) DRY=1 ;;
-r) MODE=remove ;;
"") ;;
*)
	sed -n '2,13s/^# \{0,1\}//p' "$0"
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
module_loaded() { grep -q '^v4l2loopback ' /proc/modules; }

# write_root <destino> <modo>: grava o stdin no destino como root, só se mudou.
write_root() {
	tmp=$(mktemp)
	cat > "$tmp"
	if [ -e "$1" ] && cmp -s "$tmp" "$1"; then
		echo "  = $1 já está atualizado"
	else
		as_root install -D -m "$2" "$tmp" "$1"
	fi
	rm -f "$tmp"
}

# A câmera virtual antiga da webcam USB DV20 (setup/webcam-ampla.sh, removido):
# o serviço runit dela escrevia no mesmo /dev/video10.
remove_old_webcam() {
	[ -e /var/service/webcam-ampla ] && as_root rm /var/service/webcam-ampla
	[ -d "$OLD_SV" ] && as_root rm -r "$OLD_SV"
	return 0
}

remove() {
	say "removendo o celular como webcam e microfone"
	remove_old_webcam
	for f in "$CMD" "$UDEV_RULE" "$PW_CONF" "$PULSE_CONF" "$MODPROBE_CONF" "$MODLOAD_CONF"; do
		[ -e "$f" ] && as_root rm "$f"
	done
	as_root udevadm control --reload
	if module_loaded; then as_root modprobe -r v4l2loopback; fi
	if installed v4l2loopback; then as_root xbps-remove -y v4l2loopback; fi
	say "pronto. O microfone virtual some (e o navegador volta a mudar o volume dos"
	say "microfones) ao reiniciar a sessão (PipeWire)."
	say "scrcpy e android-tools ficam instalados (o adb serve para outras coisas)."
}

if [ "$MODE" = remove ]; then
	remove
	exit 0
fi

say "pacotes"
missing=""
for pkg in scrcpy android-tools v4l2loopback; do
	installed "$pkg" || missing="$missing $pkg"
done
if [ -n "$missing" ]; then
	# shellcheck disable=SC2086 # lista de pacotes, separada por espaço de propósito
	as_root xbps-install -S $missing
else
	echo "  = já instalados"
fi

say "webcam-ampla antiga"
if [ -e /var/service/webcam-ampla ] || [ -d "$OLD_SV" ]; then
	remove_old_webcam
else
	echo "  = não está instalada"
fi

say "regra udev do adb ($UDEV_RULE)"
# O acesso ao USB do celular vem do TAG uaccess (o elogind dá a ACL ao usuário
# da sessão). As regras do sistema só marcam o modo de arquivos (MTP); no modo
# "só carregar" o celular mostra só a interface ADB (classe ff/42/01) e o adb
# dá "no permissions". Tem de vir antes do 73-seat-late.rules.
write_root "$UDEV_RULE" 0644 << 'EOF'
# Gerado por ~/dotfiles/setup/celular-webcam.sh.
# Libera ao usuário da sessão qualquer aparelho com depuração USB (interface
# ADB ff/42/01), em qualquer modo USB.
SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ENV{ID_USB_INTERFACES}=="", IMPORT{builtin}="usb_id"
SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ENV{ID_USB_INTERFACES}=="*:ff4201:*", TAG+="uaccess"
EOF
as_root udevadm control --reload
as_root udevadm trigger --action=change --subsystem-match=usb --property-match='ID_USB_INTERFACES=*:ff4201:*'

say "módulo v4l2loopback (/dev/video$VNR, \"$LABEL\")"
# exclusive_caps=1: sem isso o Chrome/Vivaldi/Meet não listam a câmera virtual.
printf 'options v4l2loopback devices=1 video_nr=%s card_label="%s" exclusive_caps=1\n' "$VNR" "$LABEL" |
	write_root "$MODPROBE_CONF" 0644
echo v4l2loopback | write_root "$MODLOAD_CONF" 0644
# Carregado com outras opções (outro /dev/videoN ou outro nome): recarrega.
name_file=/sys/devices/virtual/video4linux/video$VNR/name
if module_loaded && { [ ! -e "$name_file" ] || [ "$(cat "$name_file")" != "$LABEL" ]; }; then
	if ! as_root modprobe -r v4l2loopback; then
		echo "  ! v4l2loopback em uso (feche o que usa a câmera, ou o celular-cam) e rode de novo"
		exit 1
	fi
fi
module_loaded || as_root modprobe v4l2loopback

say "microfone virtual do PipeWire ($PW_CONF)"
# Um loopback com duas pontas de dispositivo: uma saída "$MIC_SINK", onde o
# celular-cam toca o áudio do microfone do celular, e uma entrada "$MIC_SOURCE"
# ("Microfone do celular"), de onde os apps gravam. Mono, como um microfone.
write_root "$PW_CONF" 0644 << EOF
# Gerado por ~/dotfiles/setup/celular-webcam.sh.
# Microfone virtual: o celular-cam (scrcpy) toca o microfone do celular em
# "$MIC_SINK" e os apps gravam de "$MIC_SOURCE" ("Microfone do celular").
context.modules = [
    {   name = libpipewire-module-loopback
        args = {
            node.description = "Microfone do celular"
            capture.props = {
                node.name = "$MIC_SINK"
                node.description = "Celular (entrada do microfone)"
                media.class = "Audio/Sink"
                audio.position = [ FL FR ]
            }
            playback.props = {
                node.name = "$MIC_SOURCE"
                node.description = "Microfone do celular"
                media.class = "Audio/Source"
                audio.position = [ MONO ]
            }
        }
    }
]
EOF

say "navegador sem mudar o volume dos microfones ($PULSE_CONF)"
# O controle automático de ganho do WebRTC (Meet etc.) baixa o volume da entrada
# no sistema durante a chamada. O quirk block-source-volume do pipewire-pulse
# ignora esses pedidos; o ganho digital do próprio WebRTC continua. Vale para
# os navegadores da família Chromium (o Vivaldi incluído).
write_root "$PULSE_CONF" 0644 << 'EOF'
# Gerado por ~/dotfiles/setup/celular-webcam.sh.
# Navegadores (WebRTC: Meet etc.) não mudam o volume dos microfones do sistema.
pulse.rules = [
    {
        matches = [
            { application.process.binary = "vivaldi-bin" }
            { application.process.binary = "chrome" }
            { application.process.binary = "chromium" }
        ]
        actions = { quirks = [ block-source-volume ] }
    }
]
EOF

say "comando $CMD"
# SDL_AUDIODRIVER=pipewire + PIPEWIRE_PROPS: o scrcpy cria o stream de áudio já
# com target.object na entrada do microfone virtual. Sem isso ele toca sempre
# na saída padrão (ignora PULSE_SINK) e a voz sai no alto-falante.
write_root "$CMD" 0755 << EOF
#!/bin/sh
# Gerado por ~/dotfiles/setup/celular-webcam.sh. Usa o celular Android (USB,
# depuração USB ligada) como webcam ("$LABEL", /dev/video$VNR) e microfone
# ("Microfone do celular"). Ctrl+C para parar.
#
# Uso: celular-cam [opções do scrcpy]
#   celular-cam                          câmera frontal, 1280x720, 30 fps
#   celular-cam --camera-facing=back     câmera traseira
set -eu
if ! adb get-state > /dev/null 2>&1; then
	echo "celular-cam: o adb não vê o celular (cabo, depuração USB ligada, chave autorizada?)" >&2
	exit 1
fi
if ! pactl list short sinks | awk '\$2 == "$MIC_SINK" { found = 1 } END { exit !found }'; then
	echo "celular-cam: microfone virtual ausente; reinicie a sessão (PipeWire) depois do setup/celular-webcam.sh" >&2
	exit 1
fi
SDL_AUDIODRIVER=pipewire PIPEWIRE_PROPS='{ target.object = "$MIC_SINK" }' exec scrcpy \\
	--video-source=camera --camera-facing=front --camera-size=1280x720 --camera-fps=30 \\
	--audio-source=mic --v4l2-sink=/dev/video$VNR --no-window "\$@"
EOF

[ "$DRY" = 1 ] && exit 0
if pactl list short sinks 2> /dev/null | awk -v s="$MIC_SINK" '$2 == s { found = 1 } END { exit !found }'; then
	# Desfaz o que o navegador já tenha baixado antes do quirk existir.
	pactl set-source-volume "$MIC_SOURCE" 100%
fi
say "pronto. Mudanças no PipeWire valem depois de reiniciar a sessão (ou só o PipeWire:"
say "pkill -x pipewire; setsid -f pipewire) e reabrir o navegador. Depois rode: celular-cam"
say "(no Meet: câmera \"$LABEL\", microfone \"Microfone do celular\")"
