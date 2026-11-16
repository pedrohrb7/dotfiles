#!/bin/sh
# Instala ou atualiza o MonsGeek Driver v4 (app Electron do Windows) rodando num
# Electron nativo para Linux, sem Wine, em ~/.local/share/monsgeek-driver-v4.
# Extrai a interface do instalador .exe oficial, baixa o Electron da mesma versão
# que ele embarca (conferindo o sha256), usa setup/monsgeek/linux-main.js como
# entrada e cria a entrada no menu. Precisa do iot_driver nativo servindo em
# 127.0.0.1:3814 (monsgeek-akko-linux/scripts/install-user.sh). Ver setup/README.md.
#
# Uso: setup/monsgeek-driver.sh [-n] [instalador.exe]
#   -n              só mostra o que seria feito, sem baixar nem alterar nada
#   instalador.exe  MonsGeek_V4_Driver_*.exe (padrão: o mais novo em ~/Downloads)
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
PREFIX=${XDG_DATA_HOME:-$HOME/.local/share}/monsgeek-driver-v4
APPS=${XDG_DATA_HOME:-$HOME/.local/share}/applications
BIN=monsgeek-driver-v4
DRY=0
INSTALLER=

usage() {
	sed -n '2,12s/^# \{0,1\}//p' "$0"
	exit 2
}

for arg in "$@"; do
	case "$arg" in
	-n) DRY=1 ;;
	-*) usage ;;
	*) [ -z "$INSTALLER" ] && INSTALLER=$arg || usage ;;
	esac
done

say() { printf '\033[1;35m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() {
	printf '\033[1;31m!!\033[0m %s\n' "$*" >&2
	exit 1
}
run() {
	printf '  + %s\n' "$*"
	[ "$DRY" = 1 ] || "$@"
}

for cmd in 7z curl jq sha256sum unzip truncate; do
	command -v "$cmd" > /dev/null || die "falta o comando $cmd"
done
[ -f "$HERE/monsgeek/linux-main.js" ] || die "falta $HERE/monsgeek/linux-main.js"

case "$(uname -m)" in
x86_64) ARCH=x64 ;;
aarch64) ARCH=arm64 ;;
*) die "arquitetura sem build do Electron: $(uname -m)" ;;
esac

if [ -z "$INSTALLER" ]; then
	INSTALLER=$(ls -t "$HOME"/Downloads/MonsGeek_V4_Driver_*.exe 2> /dev/null | head -n 1 || true)
	[ -n "$INSTALLER" ] ||
		die "nenhum MonsGeek_V4_Driver_*.exe em ~/Downloads; baixe o driver v4 para Windows no site da MonsGeek e passe o caminho"
fi
[ -f "$INSTALLER" ] || die "instalador não encontrado: $INSTALLER"

# Rodando de $PREFIX, o app seguraria os arquivos que vão ser trocados.
if pgrep -f "$PREFIX/$BIN" > /dev/null 2>&1; then
	die "o MonsGeek Driver v4 está aberto; feche-o antes de atualizar"
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM

# Interface do instalador -----------------------------------------------------

# O instalador é NSIS; a interface vem em $PLUGINSDIR/app-64.7z ou app-32.7z.
# A extração vai para o temporário mesmo com -n, porque é dela que saem as versões.
say "Extraindo $(basename "$INSTALLER")"
7z x -y -o"$TMP/nsis" "$INSTALLER" > /dev/null
APP7Z=$TMP/nsis/\$PLUGINSDIR/app-64.7z
[ -f "$APP7Z" ] || APP7Z=$TMP/nsis/\$PLUGINSDIR/app-32.7z
[ -f "$APP7Z" ] || die "o instalador não tem app-64.7z nem app-32.7z"
7z x -y -o"$TMP/win" "$APP7Z" > /dev/null
WINAPP=$TMP/win/resources/app
[ -f "$WINAPP/dist-electron/main.js" ] && [ -f "$WINAPP/APPVersion.json" ] ||
	die "estrutura inesperada em $(basename "$APP7Z"): falta resources/app/dist-electron/main.js"

APP_VERSION=$(jq -r .APPVersion "$WINAPP/APPVersion.json")
WINEXE=$(find "$TMP/win" -maxdepth 1 -name '*.exe' | head -n 1)
ELECTRON=$(LC_ALL=C grep -aoE 'Electron/[0-9]+\.[0-9]+\.[0-9]+' "$WINEXE" | head -n 1 | cut -d/ -f2)
[ -n "$ELECTRON" ] || die "não achei a versão do Electron em $(basename "$WINEXE")"

CURRENT_APP=$(jq -r .APPVersion "$PREFIX/resources/app/APPVersion.json" 2> /dev/null || true)
CURRENT_ELECTRON=$(cat "$PREFIX/version" 2> /dev/null || true)
printf '  instalado:  app %s, Electron %s\n' "${CURRENT_APP:-nenhum}" "${CURRENT_ELECTRON:-nenhum}"
printf '  instalador: app %s, Electron %s\n' "$APP_VERSION" "$ELECTRON"

# Electron nativo -------------------------------------------------------------

ZIP=electron-v$ELECTRON-linux-$ARCH.zip
BASE=https://github.com/electron/electron/releases/download/v$ELECTRON
say "Baixando $ZIP"
run curl -fL --progress-bar -o "$TMP/$ZIP" "$BASE/$ZIP"
run curl -fsSL -o "$TMP/SHASUMS256.txt" "$BASE/SHASUMS256.txt"
if [ "$DRY" = 0 ]; then
	SHA=$(grep " \*\{0,1\}$ZIP\$" "$TMP/SHASUMS256.txt" | cut -d' ' -f1)
	[ -n "$SHA" ] || die "$ZIP não está no SHASUMS256.txt do release"
	printf '%s  %s\n' "$SHA" "$TMP/$ZIP" | sha256sum -c --quiet - ||
		die "sha256 não confere, download descartado"
fi

# Montagem --------------------------------------------------------------------

# O binário não pode se chamar "electron": é pelo nome que o Electron decide
# app.isPackaged, e sem isso o main.js do app carrega o servidor de dev
# (localhost:8080) em vez da interface em dist/.
say "Montando o app"
run mkdir "$TMP/x"
run unzip -q "$TMP/$ZIP" -d "$TMP/x"
run mv "$TMP/x/electron" "$TMP/x/$BIN"
run cp -a "$WINAPP" "$TMP/x/resources/app"
run cp "$HERE/monsgeek/linux-main.js" "$TMP/x/resources/app/dist-electron/linux-main.js"
# A interface copia e "executa" este arquivo antes de conectar; o linux-main.js
# finge a execução e o iot_driver nativo atende em 127.0.0.1:3814.
run truncate -s 0 "$TMP/x/resources/app/iot_driver.exe"
printf '  + package.json: main -> dist-electron/linux-main.js\n'
if [ "$DRY" = 0 ]; then
	jq '.main = "dist-electron/linux-main.js"' "$TMP/x/resources/app/package.json" > "$TMP/package.json"
	mv "$TMP/package.json" "$TMP/x/resources/app/package.json"
fi

# Monta ao lado e troca de uma vez, para nunca ficar um $PREFIX pela metade.
# clickLanguage é o marcador (vazio) que a interface grava no diretório de
# trabalho quando o idioma é escolhido; passa para a instalação nova.
say "Instalando em $PREFIX"
run rm -rf "$PREFIX.new"
run cp -a "$TMP/x" "$PREFIX.new"
[ -f "$PREFIX/clickLanguage" ] && run cp "$PREFIX/clickLanguage" "$PREFIX.new/clickLanguage"
run rm -rf "$PREFIX"
run mv "$PREFIX.new" "$PREFIX"

# Menu ------------------------------------------------------------------------

desktop() {
	cat << EOF
[Desktop Entry]
Name=MonsGeek Driver v4
Comment=Configuração do teclado MonsGeek (driver oficial v4, Electron nativo)
Exec=$PREFIX/$BIN
Path=$PREFIX
Icon=$PREFIX/resources/app/company/company_MonsGeek/icon.png
Type=Application
Categories=Settings;HardwareSettings;
Keywords=monsgeek;keyboard;teclado;
EOF
}

say "Entrada em $APPS"
run mkdir -p "$APPS"
printf '  + escreve %s\n' "$APPS/$BIN.desktop"
[ "$DRY" = 1 ] || desktop > "$APPS/$BIN.desktop"
command -v update-desktop-database > /dev/null &&
	run update-desktop-database "$APPS"

# iot_driver nativo -------------------------------------------------------------

if command -v ss > /dev/null && ! ss -ltn 2> /dev/null | grep -q '127.0.0.1:3814 '; then
	warn "nada escutando em 127.0.0.1:3814: sem o iot_driver nativo o app fica em 'procurando dispositivos'; instale com $HERE/../monsgeek-akko-linux/scripts/install-user.sh"
fi

say "Pronto: $PREFIX/$BIN (ou 'MonsGeek Driver v4' no menu)"
