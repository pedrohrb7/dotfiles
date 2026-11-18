#!/bin/sh
# Celular Android antigo (Galaxy J5 Prime, Android 8) como webcam e microfone,
# pelo app IP Webcam. O celular-cam (scrcpy) só pega a câmera do Android 12 em
# diante e o microfone do 11 em diante; aqui o app transmite e o ffmpeg joga o
# vídeo na câmera virtual "Celular" (/dev/video10) e o áudio no "Microfone do
# celular", os dois criados pelo setup/celular-webcam.sh (rode ele antes).
#
# Uso: setup/j5-cam.sh [-v] [-r 90|180|270] [ip[:porta]]
#   sem ip   pelo cabo USB (adb, depuração USB ligada)
#   ip       pelo Wi-Fi, no endereço que o app mostra (ex.: 192.168.0.12:8080)
#   -v       só vídeo, sem o microfone
#   -r N     gira a imagem N graus no sentido horário
#
# No celular: abra o IP Webcam, escolha a câmera e a resolução nas configurações
# do app e toque em "Iniciar servidor". Ctrl+C para parar.
set -eu

VDEV=/dev/video10
LABEL="Celular"
MIC_SINK=celular_mic_entrada
APP_PORT=8080
# Porta local do adb forward; não a 8080, comum em servidores de desenvolvimento.
LOCAL_PORT=18080
AUDIO=1

usage() {
	sed -n '2,15s/^# \{0,1\}//p' "$0"
	exit 2
}

say() { printf '\033[1;35m==>\033[0m %s\n' "$*"; }
die() {
	echo "j5-cam: $*" >&2
	exit 1
}

ROTATE=""
while getopts vr: opt; do
	case "$opt" in
	v) AUDIO=0 ;;
	r)
		case "$OPTARG" in
		90) ROTATE="transpose=clock," ;;
		180) ROTATE="hflip,vflip," ;;
		270) ROTATE="transpose=cclock," ;;
		*) usage ;;
		esac
		;;
	*) usage ;;
	esac
done
shift $((OPTIND - 1))
[ $# -le 1 ] || usage
HOST="${1:-}"

for bin in ffmpeg curl; do
	command -v "$bin" > /dev/null || die "falta o $bin"
done
name_file=/sys/devices/virtual/video4linux/${VDEV#/dev/}/name
if [ ! -e "$name_file" ] || [ "$(cat "$name_file")" != "$LABEL" ]; then
	die "câmera virtual \"$LABEL\" ($VDEV) ausente; rode setup/celular-webcam.sh"
fi
if [ "$AUDIO" = 1 ] && ! pactl list short sinks | awk -v s="$MIC_SINK" '$2 == s { found = 1 } END { exit !found }'; then
	die "microfone virtual ausente; reinicie a sessão (PipeWire) depois do setup/celular-webcam.sh, ou use -v"
fi

FORWARD=0
pids=""
cleanup() {
	trap - EXIT INT TERM
	# shellcheck disable=SC2086 # lista de pids, separada por espaço de propósito
	[ -z "$pids" ] || kill $pids 2> /dev/null || true
	[ "$FORWARD" = 0 ] || adb forward --remove "tcp:$LOCAL_PORT" > /dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if [ -n "$HOST" ]; then
	case "$HOST" in
	*:*) BASE="http://$HOST" ;;
	*) BASE="http://$HOST:$APP_PORT" ;;
	esac
else
	command -v adb > /dev/null || die "falta o adb"
	adb get-state > /dev/null 2>&1 ||
		die "o adb não vê o celular (cabo de dados, depuração USB ligada, chave autorizada?); pelo Wi-Fi: j5-cam.sh <ip>"
	adb forward "tcp:$LOCAL_PORT" "tcp:$APP_PORT" > /dev/null
	FORWARD=1
	BASE="http://127.0.0.1:$LOCAL_PORT"
fi

curl -s -o /dev/null --max-time 5 "$BASE/" ||
	die "o IP Webcam não responde em $BASE (abra o app e toque em \"Iniciar servidor\")"

# Reconecta sozinho se o Wi-Fi ou o app piscarem.
IN_OPTS="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -fflags nobuffer -flags low_delay"

say "vídeo: $BASE/video -> $VDEV (\"$LABEL\")"
# shellcheck disable=SC2086 # opções de entrada, separadas por espaço de propósito
ffmpeg -hide_banner -loglevel error -nostdin $IN_OPTS -i "$BASE/video" \
	-vf "${ROTATE}format=yuv420p" -f v4l2 "$VDEV" &
pids="$!"

if [ "$AUDIO" = 1 ]; then
	say "microfone: $BASE/audio.wav -> \"Microfone do celular\""
	# shellcheck disable=SC2086 # opções de entrada, separadas por espaço de propósito
	ffmpeg -hide_banner -loglevel error -nostdin $IN_OPTS -i "$BASE/audio.wav" \
		-f pulse -device "$MIC_SINK" "j5-cam" &
	pids="$pids $!"
fi

if [ "$AUDIO" = 1 ]; then
	say "no Meet: câmera \"$LABEL\", microfone \"Microfone do celular\". Ctrl+C para parar."
else
	say "no Meet: câmera \"$LABEL\". Ctrl+C para parar."
fi
# Para tudo quando qualquer um dos ffmpeg terminar.
while :; do
	for pid in $pids; do
		kill -0 "$pid" 2> /dev/null || die "a transmissão caiu (o app foi fechado ou o celular desconectou?)"
	done
	sleep 1
done
