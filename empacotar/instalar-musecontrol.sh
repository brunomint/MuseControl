#!/usr/bin/env bash
# Instalador do MuseControl para Linux (sem precisar de senha de administrador).
#
#   bash instalar-musecontrol.sh            instala ou atualiza
#   bash instalar-musecontrol.sh --remover  desinstala (os seus projetos ficam)
#
# Instala em ~/.local/share/musecontrol, coloca o MuseControl no menu de
# aplicativos e cria o comando "musecontrol". Os projetos e variáveis ficam em
# ~/.local/share/musecontrol/dados e não são apagados ao atualizar.
#
# Opções (variáveis de ambiente):
#   MUSECONTROL_VERSAO=v2.0.0       versão (padrão: a mais nova publicada)
#   MUSECONTROL_ARQUIVO=x.tar.gz    instala de um arquivo local (sem internet)
#   MUSECONTROL_LIGAR_COM_PC=s|n    responde a pergunta sobre ligar com o PC
set -euo pipefail

REPO="brunomint/MuseControl"
BASE="${XDG_DATA_HOME:-$HOME/.local/share}/musecontrol"
APP="$BASE/app"
VENV="$BASE/venv"
DADOS="$BASE/dados"
BIN="$HOME/.local/bin"
COMANDO="$BIN/musecontrol"
ATALHO="${XDG_DATA_HOME:-$HOME/.local/share}/applications/musecontrol.desktop"
SERVICO="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/musecontrol.service"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
erro() { printf '\033[1;31mErro:\033[0m %s\n' "$*" >&2; exit 1; }

remover() {
    info "Desinstalando o MuseControl…"
    if command -v systemctl >/dev/null && [ -f "$SERVICO" ]; then
        systemctl --user disable --now musecontrol.service 2>/dev/null || true
        rm -f "$SERVICO"
        systemctl --user daemon-reload 2>/dev/null || true
    fi
    rm -rf "$APP" "$VENV"
    rm -f "$COMANDO" "$ATALHO"
    info "Pronto. Os seus projetos continuam em $DADOS (apague à mão se quiser)."
    exit 0
}
[ "${1:-}" = "--remover" ] && remover

# ---- 1. Python ------------------------------------------------------------------
command -v python3 >/dev/null || erro "precisa do Python 3. No Ubuntu/Mint: sudo apt install python3 python3-venv"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
    || erro "precisa do Python 3.9 ou mais novo (tem $(python3 -V))"
python3 -c 'import venv, ensurepip' 2>/dev/null \
    || erro "falta o venv do Python. No Ubuntu/Mint: sudo apt install python3-venv"

# ---- 2. Baixar o programa ---------------------------------------------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if [ -n "${MUSECONTROL_ARQUIVO:-}" ]; then
    info "Usando o arquivo $MUSECONTROL_ARQUIVO"
    cp "$MUSECONTROL_ARQUIVO" "$TMP/musecontrol.tar.gz"
else
    command -v curl >/dev/null || erro "precisa do curl. No Ubuntu/Mint: sudo apt install curl"
    VERSAO="${MUSECONTROL_VERSAO:-}"
    if [ -z "$VERSAO" ]; then
        VERSAO="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
            | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)"
        VERSAO="${VERSAO:-main}"
    fi
    info "Baixando o MuseControl ($VERSAO)…"
    curl -fsSL "https://github.com/$REPO/archive/$VERSAO.tar.gz" -o "$TMP/musecontrol.tar.gz" \
        || erro "não consegui baixar a versão $VERSAO"
fi
mkdir -p "$TMP/x"
tar -xzf "$TMP/musecontrol.tar.gz" -C "$TMP/x"
ORIGEM="$(dirname "$(find "$TMP/x" -maxdepth 2 -name main.py -print -quit)")"
[ -f "$ORIGEM/main.py" ] || erro "o arquivo baixado não parece ser o MuseControl"

# ---- 3. Copiar (os dados ficam fora da pasta do programa) -------------------------------
info "Instalando em $APP"
mkdir -p "$BASE" "$DADOS"
rm -rf "$APP"
mkdir -p "$APP"
for item in main.py caminhos.py banco.py pulsacao.py variaveis.py projetos.py requirements.txt templates static; do
    [ -e "$ORIGEM/$item" ] && cp -r "$ORIGEM/$item" "$APP/"
done

# ---- 4. Ambiente Python ---------------------------------------------------------------
info "Preparando o Python (pode levar um minuto na primeira vez)…"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$APP/requirements.txt"

# ---- 5. Comando, menu de aplicativos ---------------------------------------------------
mkdir -p "$BIN" "$(dirname "$ATALHO")"
cat > "$COMANDO" <<EOF2
#!/usr/bin/env bash
# MuseControl (criado pelo instalador)
export MUSECONTROL_DADOS="$DADOS"
cd "$APP"
exec "$VENV/bin/python" main.py "\$@"
EOF2
chmod +x "$COMANDO"

cat > "$ATALHO" <<EOF2
[Desktop Entry]
Type=Application
Name=MuseControl
Comment=Escreva partitura no MuseScore marcando o pulso
Exec=$COMANDO
Icon=$APP/static/icone.png
Terminal=false
Categories=AudioVideo;Audio;Music;
EOF2
command -v update-desktop-database >/dev/null && update-desktop-database "$(dirname "$ATALHO")" 2>/dev/null || true

# ---- 6. Ligar junto com o computador? --------------------------------------------------
resposta="${MUSECONTROL_LIGAR_COM_PC:-}"
if [ -z "$resposta" ] && [ -r /dev/tty ]; then
    printf 'Ligar o MuseControl sozinho quando o computador ligar? [s/N] '
    read -r resposta < /dev/tty || resposta=n
fi
if [[ "${resposta:-n}" =~ ^[sSyY] ]] && command -v systemctl >/dev/null; then
    mkdir -p "$(dirname "$SERVICO")"
    cat > "$SERVICO" <<EOF2
[Unit]
Description=MuseControl (escrever partitura pelo celular)
After=graphical-session.target

[Service]
Environment=MUSECONTROL_NAO_ABRIR=1
ExecStart=$COMANDO
Restart=on-failure

[Install]
WantedBy=default.target
EOF2
    systemctl --user daemon-reload
    systemctl --user enable --now musecontrol.service
    info "Vai ligar sozinho com o computador (para desligar isso: systemctl --user disable musecontrol)"
fi

echo
info "MuseControl instalado!"
echo "    Abra pelo menu de aplicativos (MuseControl) ou digite: musecontrol"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "    (para o comando funcionar, saia e entre de novo na sessão)";; esac
echo "    Os seus projetos ficam em: $DADOS"
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    echo "    Aviso: na sessão Wayland, digitar no MuseScore pode não funcionar."
    echo "    Use a sessão X11 (Xorg) ao entrar no computador."
fi
