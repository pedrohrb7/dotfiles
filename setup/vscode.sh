#!/bin/sh
# Instala ou atualiza o Visual Studio Code oficial (tarball da Microsoft) em
# /opt/vscode, que é o que o .zshrc põe no PATH (/opt/vscode/bin/code).
# Confere o sha256 do download, cria a entrada no menu e o handler de links
# vscode:// em ~/.local/share/applications. Se a versão instalada já é a
# mais nova, não faz nada. Ver setup/README.md.
#
# Uso: setup/vscode.sh [-n]
#   -n  só mostra o que seria feito, sem baixar nem alterar nada
set -eu

PREFIX=/opt/vscode
APPS=${XDG_DATA_HOME:-$HOME/.local/share}/applications
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
die() {
	printf '\033[1;31m!!\033[0m %s\n' "$*" >&2
	exit 1
}
run() {
	printf '  + %s\n' "$*"
	[ "$DRY" = 1 ] || "$@"
}
as_root() {
	if [ "$(id -u)" = 0 ]; then run "$@"; else run sudo "$@"; fi
}

for cmd in curl jq tar sha256sum; do
	command -v "$cmd" > /dev/null || die "falta o comando $cmd"
done

case "$(uname -m)" in
x86_64) ARCH=x64 ;;
aarch64) ARCH=arm64 ;;
armv7l) ARCH=armhf ;;
*) die "arquitetura sem build do VSCode: $(uname -m)" ;;
esac

# Versão --------------------------------------------------------------------

say "Consultando a última versão (linux-$ARCH, stable)"
META=$(curl -fsSL "https://update.code.visualstudio.com/api/update/linux-$ARCH/stable/latest")
LATEST=$(printf '%s' "$META" | jq -r .productVersion)
URL=$(printf '%s' "$META" | jq -r .url)
SHA=$(printf '%s' "$META" | jq -r .sha256hash)
[ -n "$LATEST" ] && [ "$URL" != null ] && [ "$SHA" != null ] ||
	die "resposta inesperada da API de update"

CURRENT=$(jq -r .version "$PREFIX/resources/app/package.json" 2> /dev/null || true)
printf '  instalada: %s\n  última:    %s\n' "${CURRENT:-nenhuma}" "$LATEST"

# Instalação ----------------------------------------------------------------

if [ "$CURRENT" = "$LATEST" ]; then
	say "Já está na última versão"
else
	TMP=$(mktemp -d)
	trap 'rm -rf "$TMP"' EXIT INT TERM

	say "Baixando $LATEST"
	run curl -fL --progress-bar -o "$TMP/code.tar.gz" "$URL"
	if [ "$DRY" = 0 ]; then
		printf '%s  %s\n' "$SHA" "$TMP/code.tar.gz" | sha256sum -c --quiet - ||
			die "sha256 não confere, download descartado"
	fi

	# O tarball tem uma pasta VSCode-linux-<arch>/. Extrai ao lado e troca de
	# uma vez, para nunca ficar um /opt/vscode pela metade.
	say "Instalando em $PREFIX"
	run mkdir "$TMP/x"
	run tar -xzf "$TMP/code.tar.gz" -C "$TMP/x" --strip-components=1
	as_root rm -rf "$PREFIX.new"
	as_root cp -a "$TMP/x" "$PREFIX.new"
	as_root chown -R root:root "$PREFIX.new"
	as_root rm -rf "$PREFIX"
	as_root mv "$PREFIX.new" "$PREFIX"
fi

# Menu e links vscode:// ----------------------------------------------------

ICON=$PREFIX/resources/app/resources/linux/code.png

desktop_main() {
	cat << EOF
[Desktop Entry]
Name=Visual Studio Code
Comment=Code Editing. Redefined.
GenericName=Text Editor
Exec=$PREFIX/bin/code %F
Icon=$ICON
Type=Application
StartupNotify=false
StartupWMClass=Code
Categories=TextEditor;Development;IDE;
MimeType=text/plain;inode/directory;application/x-code-workspace;
Actions=new-empty-window;
Keywords=vscode;

[Desktop Action new-empty-window]
Name=New Empty Window
Exec=$PREFIX/bin/code --new-window %F
Icon=$ICON
EOF
}

# Usado pelo login das extensões (GitHub, Microsoft) que voltam por vscode://.
desktop_url() {
	cat << EOF
[Desktop Entry]
Name=Visual Studio Code - URL Handler
Comment=Code Editing. Redefined.
GenericName=Text Editor
Exec=$PREFIX/bin/code --open-url %U
Icon=$ICON
Type=Application
NoDisplay=true
StartupNotify=true
Categories=Utility;TextEditor;Development;IDE;
MimeType=x-scheme-handler/vscode;
Keywords=vscode;
EOF
}

say "Entradas em $APPS"
run mkdir -p "$APPS"
printf '  + escreve %s\n' "$APPS/code.desktop" "$APPS/code-url-handler.desktop"
if [ "$DRY" = 0 ]; then
	desktop_main > "$APPS/code.desktop"
	desktop_url > "$APPS/code-url-handler.desktop"
fi
command -v update-desktop-database > /dev/null &&
	run update-desktop-database "$APPS"
command -v xdg-mime > /dev/null &&
	run xdg-mime default code-url-handler.desktop x-scheme-handler/vscode

say "Pronto: $PREFIX/bin/code (abra um terminal novo se 'code' não for encontrado)"
