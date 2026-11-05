#!/bin/sh
# Câmera virtual "Webcam ampla" (/dev/video10) para a webcam USB DV20 (Jieli).
# O modo 16:9 da câmera (1280x720) é um recorte do sensor e deixa a imagem
# perto demais; o 640x480 mostra o campo inteiro. Um serviço runit lê o
# 640x480 e entrega no v4l2loopback em 16:9 (854x480) com faixas pretas nas
# laterais, sem cortar nada (cortar para 16:9 volta a parecer zoom).
# Pode rodar quantas vezes quiser. Ver setup/README.md.
#
# Uso: setup/webcam-ampla.sh [-n | -r]
#   -n  só mostra o que seria feito, sem instalar nem alterar nada
#   -r  remove tudo (serviço, confs do módulo e o pacote v4l2loopback)
set -eu

CAM=/dev/v4l/by-id/usb-Jieli_Technology_USB_Composite_Device-video-index0
VNR=10
LABEL="Webcam ampla"
SV=/etc/sv/webcam-ampla
MODPROBE_CONF=/etc/modprobe.d/v4l2loopback.conf
MODLOAD_CONF=/etc/modules-load.d/v4l2loopback.conf
DRY=0
MODE=install

case "${1:-}" in
-n) DRY=1 ;;
-r) MODE=remove ;;
"") ;;
*)
	sed -n '2,11s/^# \{0,1\}//p' "$0"
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

remove() {
	say "removendo a Webcam ampla"
	[ -e /var/service/webcam-ampla ] && as_root rm /var/service/webcam-ampla
	[ -d "$SV" ] && as_root rm -r "$SV"
	[ -e "$MODPROBE_CONF" ] && as_root rm "$MODPROBE_CONF"
	[ -e "$MODLOAD_CONF" ] && as_root rm "$MODLOAD_CONF"
	if grep -q '^v4l2loopback ' /proc/modules; then as_root modprobe -r v4l2loopback; fi
	if installed v4l2loopback; then as_root xbps-remove -y v4l2loopback; fi
	say "pronto"
}

if [ "$MODE" = remove ]; then
	remove
	exit 0
fi

[ -e "$CAM" ] || echo "  ! $CAM não existe agora (webcam desconectada?). O serviço espera ela aparecer."

say "pacotes"
missing=""
for pkg in v4l2loopback v4l-utils ffmpeg; do
	installed "$pkg" || missing="$missing $pkg"
done
if [ -n "$missing" ]; then
	# shellcheck disable=SC2086 # lista de pacotes, separada por espaço de propósito
	as_root xbps-install -S $missing
else
	echo "  = já instalados"
fi

say "módulo v4l2loopback (/dev/video$VNR, \"$LABEL\")"
# exclusive_caps=1: sem isso o Chrome/Vivaldi/Meet não listam a câmera virtual.
printf 'options v4l2loopback devices=1 video_nr=%s card_label="%s" exclusive_caps=1\n' "$VNR" "$LABEL" |
	write_root "$MODPROBE_CONF" 0644
echo v4l2loopback | write_root "$MODLOAD_CONF" 0644
# Carregado com outras opções (sem o /dev/videoN certo): recarrega.
if grep -q '^v4l2loopback ' /proc/modules && [ ! -e "/dev/video$VNR" ]; then
	as_root modprobe -r v4l2loopback
fi
grep -q '^v4l2loopback ' /proc/modules || as_root modprobe v4l2loopback

say "serviço runit webcam-ampla"
write_root "$SV/run" 0755 << EOF
#!/bin/sh
# Gerado por ~/dotfiles/setup/webcam-ampla.sh. Lê o modo 640x480 completo da
# webcam USB e entrega 16:9 (854x480, faixas pretas nas laterais) em /dev/video$VNR.
CAM=$CAM
exec 2>&1
[ -e "\$CAM" ] || { sleep 5; exit 1; }
# A câmera às vezes trava mandando só quadros corrompidos, e aí o ffmpeg espera
# para sempre. Se 5 quadros não chegam em 8 s, desconecta e reconecta a USB
# (como tirar e pôr o cabo) e deixa o runit tentar de novo.
if ! timeout 8 ffmpeg -nostdin -loglevel quiet -f v4l2 -input_format mjpeg \\
	-video_size 640x480 -i "\$CAM" -frames:v 5 -f null -; then
	usb=\$(readlink -f "/sys/class/video4linux/\$(basename "\$(readlink -f "\$CAM")")/device/..")
	echo "webcam sem imagem; reconectando \$usb"
	echo 0 > "\$usb/authorized"
	sleep 1
	echo 1 > "\$usb/authorized"
	sleep 3
	exit 1
fi
# A câmera liga com contraste, saturação e nitidez zerados.
v4l2-ctl -d "\$CAM" --set-ctrl=contrast=256,saturation=256,sharpness=128
# loglevel fatal: o MJPEG desta câmera gera "unable to decode APP fields" em
# todo quadro (inofensivo). Se o ffmpeg cair, o runit sobe ele de novo.
exec ffmpeg -hide_banner -nostdin -loglevel fatal \\
	-f v4l2 -input_format mjpeg -video_size 640x480 -framerate 30 -i "\$CAM" \\
	-vf "pad=854:480:(ow-iw)/2:0,format=yuv420p" -f v4l2 /dev/video$VNR
EOF
if [ -e /var/service/webcam-ampla ]; then
	as_root sv restart webcam-ampla
else
	as_root ln -s "$SV" /var/service/
fi

[ "$DRY" = 1 ] && exit 0
# O runsvdir olha o /var/service a cada 5 s; até lá não existe supervise/ok
# (a pasta supervise só é legível pelo root).
supervised() {
	if [ "$(id -u)" = 0 ]; then test -e "$SV/supervise/ok"; else sudo test -e "$SV/supervise/ok"; fi
}
for _ in 1 2 3 4 5 6 7 8 9 10; do
	supervised && break
	sleep 1
done
as_root sv status webcam-ampla
say "pronto. Teste com: ffplay /dev/video$VNR  (no Meet: Configurações > Vídeo > \"$LABEL\")"
say "desligar/religar a webcam: sudo sv down webcam-ampla / sudo sv up webcam-ampla"
