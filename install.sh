#!/usr/bin/env bash
# ============================================================
#  XoloC2 — Installer
#  Usage: bash install.sh [--port PORT] [--host HOST]
#  Default: HTTPS on port 8443
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
CYN='\033[0;36m'
MAG='\033[0;35m'
BLD='\033[1m'
RST='\033[0m'

XOLO_PORT=8443
XOLO_HOST="0.0.0.0"
_PORT_SET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) XOLO_PORT="$2"; _PORT_SET=1; shift 2 ;;
    --host) XOLO_HOST="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Interactive port prompt (skipped if --port was passed) ───────────────────
if [[ $_PORT_SET -eq 0 ]]; then
  echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
  while true; do
    read -rp "$(echo -e "  ${BLD}Puerto HTTPS${RST} [${YLW}${XOLO_PORT}${RST}]: ")" _INPUT
    _INPUT="${_INPUT:-$XOLO_PORT}"
    if [[ "$_INPUT" =~ ^[0-9]+$ ]] && (( _INPUT >= 1 && _INPUT <= 65535 )); then
      XOLO_PORT="$_INPUT"
      break
    else
      echo -e "  ${RED}[!] Puerto inválido. Usa un número entre 1 y 65535.${RST}"
    fi
  done
  echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
  echo ""
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/server"
CERT_DIR="$SERVER_DIR/certs"

echo ""
echo -e "${MAG}${BLD}"
cat << 'LOGO'
██╗  ██╗ ██████╗ ██╗      ██████╗  ██████╗██████╗
╚██╗██╔╝██╔═══██╗██║     ██╔═══██╗██╔════╝╚════██╗
 ╚███╔╝ ██║   ██║██║     ██║   ██║██║      █████╔╝
 ██╔██╗ ██║   ██║██║     ██║   ██║██║     ██╔═══╝
██╔╝ ██╗╚██████╔╝███████╗╚██████╔╝╚██████╗███████╗
╚═╝  ╚═╝ ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝╚══════╝
          Command & Control Framework
LOGO
echo -e "${RST}"
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "${YLW}[*] Installing XoloC2 on port ${XOLO_PORT} (HTTPS)${RST}"
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

# ── Python check ─────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}[!] Python 3 not found. Install it first.${RST}"
  exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GRN}[✓] Python ${PY_VER} found${RST}"

# ── OpenSSL check ─────────────────────────────────────────
if ! command -v openssl &>/dev/null; then
  echo -e "${RED}[!] openssl not found. Install it first.${RST}"
  exit 1
fi

# ── Virtual environment ───────────────────────────────────
VENV="$SCRIPT_DIR/.venv"
if [[ ! -d "$VENV" ]]; then
  echo -e "${YLW}[*] Creating virtual environment...${RST}"
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"
"$VENV/bin/pip" install --quiet -r "$SERVER_DIR/requirements.txt"
echo -e "${GRN}[✓] Dependencies installed${RST}"

# ── Optional: JDK (for server-side JAR compilation) ──────
echo ""
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  ${BLD}Java JDK${RST} — necesario para compilar beacons ${YLW}.jar${RST} en el servidor."
if command -v javac &>/dev/null; then
  echo -e "  ${GRN}[✓] JDK ya instalado: $(javac -version 2>&1)${RST}"
else
  read -rp "$(echo -e "  ¿Instalar JDK? [${YLW}s/N${RST}] (default: N): ")" _INST_JDK
  _INST_JDK="${_INST_JDK:-N}"
  if [[ "$_INST_JDK" =~ ^[sS]$ ]]; then
    echo -e "${YLW}[*] Instalando default-jdk...${RST}"
    apt-get install -y default-jdk 2>/dev/null || { echo -e "${RED}[!] Fallo al instalar JDK. Instálalo manualmente: apt install default-jdk${RST}"; }
    command -v javac &>/dev/null && echo -e "${GRN}[✓] JDK instalado: $(javac -version 2>&1)${RST}" || echo -e "${RED}[!] javac no encontrado tras instalación${RST}"
  else
    echo -e "${YLW}[~] JDK omitido — compilación de .jar no disponible${RST}"
  fi
fi
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"

# ── Optional: Go (for server-side Go beacon compilation) ─
echo ""
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  ${BLD}Go compiler${RST} — necesario para compilar beacons Go ${YLW}Linux ELF / Windows EXE${RST}."
echo -e "  ${YLW}Nota:${RST} Se requiere Go ≥ 1.21. Se instalará desde go.dev si no está presente."
_GO_OK=0
if command -v go &>/dev/null; then
  _GOVER=$(go version | awk '{print $3}' | sed 's/go//')
  _GOMAJ=$(echo "$_GOVER" | cut -d. -f1)
  _GOMIN=$(echo "$_GOVER" | cut -d. -f2)
  if (( _GOMAJ > 1 || (_GOMAJ == 1 && _GOMIN >= 21) )); then
    echo -e "  ${GRN}[✓] Go $_GOVER ya instalado y es compatible${RST}"
    _GO_OK=1
  else
    echo -e "  ${YLW}[~] Go $_GOVER encontrado pero es < 1.21 — se recomienda actualizar${RST}"
  fi
fi
if [[ $_GO_OK -eq 0 ]]; then
  read -rp "$(echo -e "  ¿Instalar Go 1.22.4 desde go.dev? [${YLW}s/N${RST}] (default: N): ")" _INST_GO
  _INST_GO="${_INST_GO:-N}"
  if [[ "$_INST_GO" =~ ^[sS]$ ]]; then
    _GO_TAR="go1.22.4.linux-amd64.tar.gz"
    _GO_URL="https://go.dev/dl/${_GO_TAR}"
    _GO_TMP="/tmp/${_GO_TAR}"
    echo -e "${YLW}[*] Descargando Go 1.22.4...${RST}"
    if curl -fsSL "$_GO_URL" -o "$_GO_TMP"; then
      rm -rf /usr/local/go
      tar -C /usr/local -xzf "$_GO_TMP"
      rm -f "$_GO_TMP"
      # Add to PATH for current session and for start.sh
      export PATH=$PATH:/usr/local/go/bin
      # Persist in /etc/profile.d
      echo 'export PATH=$PATH:/usr/local/go/bin' > /etc/profile.d/golang.sh
      command -v go &>/dev/null && echo -e "${GRN}[✓] Go instalado: $(go version)${RST}" || echo -e "${RED}[!] go no encontrado tras instalación${RST}"
    else
      echo -e "${RED}[!] Descarga fallida. Instala Go manualmente desde https://go.dev/dl/${RST}"
    fi
  else
    echo -e "${YLW}[~] Go omitido — compilación de beacons Go no disponible${RST}"
  fi
fi
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

# ── TLS certificate ────────────────────────────────────────
mkdir -p "$CERT_DIR"
CERT="$CERT_DIR/cert.pem"
KEY="$CERT_DIR/key.pem"

_USE_LETSENCRYPT=0
_TRUST_PROXY=0

# ── TLS mode ─────────────────────────────────────────────────
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  ${BLD}Tipo de certificado TLS:${RST}"
echo -e "    ${YLW}[L]${RST} Let's Encrypt  (requiere dominio + certbot + puerto 80 libre)"
echo -e "    ${YLW}[A]${RST} Autofirmado    (sin requisitos adicionales)"
read -rp "$(echo -e "  Elige [${YLW}L/A${RST}] (default: A): ")" _CERT_CHOICE
_CERT_CHOICE="${_CERT_CHOICE:-A}"
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

if [[ "$_CERT_CHOICE" =~ ^[lL]$ ]]; then
  if ! command -v certbot &>/dev/null; then
    echo -e "${RED}[!] certbot no está instalado. Instálalo con: apt install certbot${RST}"
    echo -e "${YLW}    Continuando con certificado autofirmado...${RST}"
  else
    read -rp "$(echo -e "  ${BLD}Dominio${RST} (ej: c2.ejemplo.com): ")" _DOMAIN
    _DOMAIN="${_DOMAIN:-}"
    if [[ -z "$_DOMAIN" ]]; then
      echo -e "${RED}[!] Dominio vacío — se usará certificado autofirmado.${RST}"
    else
      read -rp "$(echo -e "  ${BLD}Email Let's Encrypt${RST} (notificaciones de expiración): ")" _LE_EMAIL
      _LE_EMAIL="${_LE_EMAIL:-admin@${_DOMAIN}}"

      echo -e "${YLW}[*] Obteniendo certificado Let's Encrypt para ${_DOMAIN}...${RST}"
      echo -e "${YLW}    (certbot usará el puerto 80 brevemente)${RST}"

      if certbot certonly --standalone \
          -d "$_DOMAIN" \
          --non-interactive \
          --agree-tos \
          -m "$_LE_EMAIL" \
          --preferred-challenges http; then

        cp -f "/etc/letsencrypt/live/${_DOMAIN}/fullchain.pem" "$CERT"
        cp -f "/etc/letsencrypt/live/${_DOMAIN}/privkey.pem"   "$KEY"
        chmod 600 "$KEY"
        echo -e "${GRN}[✓] Certificado Let's Encrypt obtenido y copiado${RST}"
        _USE_LETSENCRYPT=1

        # ── Renewal deploy hook ────────────────────────────────
        HOOK_DIR="/etc/letsencrypt/renewal-hooks/deploy"
        HOOK_FILE="$HOOK_DIR/xoloc2.sh"
        mkdir -p "$HOOK_DIR"
        cat > "$HOOK_FILE" <<HOOKEOF
#!/usr/bin/env bash
# XoloC2 Let's Encrypt renewal deploy hook — auto-generated by install.sh
CERT_DIR="${CERT_DIR}"
DOMAIN="${_DOMAIN}"
cp -f "/etc/letsencrypt/live/\${DOMAIN}/fullchain.pem" "\${CERT_DIR}/cert.pem"
cp -f "/etc/letsencrypt/live/\${DOMAIN}/privkey.pem"   "\${CERT_DIR}/key.pem"
chmod 600 "\${CERT_DIR}/key.pem"
if systemctl is-active --quiet xoloc2 2>/dev/null; then
  systemctl restart xoloc2
fi
HOOKEOF
        chmod +x "$HOOK_FILE"
        echo -e "${GRN}[✓] Deploy hook de renovación creado en ${HOOK_FILE}${RST}"
      else
        echo -e "${RED}[!] certbot falló — asegúrate de que el puerto 80 esté libre y el dominio apunte a esta IP.${RST}"
        echo -e "${YLW}    Continuando con certificado autofirmado...${RST}"
      fi
    fi
  fi
fi

# ── Fallback: self-signed cert ────────────────────────────────
if [[ $_USE_LETSENCRYPT -eq 0 ]]; then
  if [[ ! -f "$CERT" ]] || [[ ! -f "$KEY" ]]; then
    echo -e "${YLW}[*] Generando certificado TLS autofirmado (RSA 4096, 10 años)...${RST}"
    openssl req -x509 -newkey rsa:4096 -keyout "$KEY" -out "$CERT" \
      -days 3650 -nodes -subj "/CN=xolo-c2/O=XoloC2/C=MX" \
      -addext "subjectAltName=IP:127.0.0.1,IP:0.0.0.0" 2>/dev/null
    chmod 600 "$KEY"
    echo -e "${GRN}[✓] Certificado autofirmado generado${RST}"
  else
    echo -e "${GRN}[✓] Certificado TLS ya existe${RST}"
  fi
fi

# ── Reverse proxy ─────────────────────────────────────────────
# IMPORTANT: If uvicorn is exposed directly (no nginx/Caddy in front), the IP whitelist
# can be bypassed by any client that sends a spoofed X-Real-IP header.
# Only enable TRUST_PROXY if a reverse proxy that sets X-Real-IP from $remote_addr is in use.
echo ""
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  ${BLD}¿Correrá uvicorn detrás de un reverse proxy (nginx/Caddy)?${RST}"
echo -e "  ${YLW}⚠  Si dices S pero no hay proxy, el whitelist de IP puede ser bypasseado.${RST}"
read -rp "$(echo -e "  [${YLW}s/N${RST}] (default: N): ")" _HAS_PROXY
_HAS_PROXY="${_HAS_PROXY:-N}"
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

if [[ "$_HAS_PROXY" =~ ^[sS]$ ]]; then
  _TRUST_PROXY=1
  echo -e "${GRN}[✓] Modo proxy: se confiará en X-Real-IP para el whitelist${RST}"
else
  echo -e "${GRN}[✓] Modo directo: se usará la IP TCP real (X-Real-IP ignorada)${RST}"
fi

# ── Generate admin password (only alphanumeric + safe symbols, no $ or `) ──
# NOTE: password is passed via env var to avoid bash heredoc expansion issues
ADMIN_PASS=$(python3 -c "import os; print(os.urandom(16).hex())")

# ── Bootstrap DB / admin user ─────────────────────────────
# Use quoted heredoc (<<'PYEOF') + env var so special chars in password
# are never interpreted by bash.
cd "$SERVER_DIR"

XOLO_ADMIN_PASS="$ADMIN_PASS" python3 - <<'PYEOF'
import sys, os
sys.path.insert(0, os.getcwd())
from database import init_db, SessionLocal, User
from auth import hash_password

admin_pass = os.environ['XOLO_ADMIN_PASS']

init_db()
db = SessionLocal()

existing = db.query(User).filter(User.username == 'admin').first()
if existing:
    # Reset password on reinstall
    existing.password_hash = hash_password(admin_pass)
    existing.must_change_password = True
    db.commit()
else:
    user = User(
        username='admin',
        password_hash=hash_password(admin_pass),
        must_change_password=True,
    )
    db.add(user)
    db.commit()
db.close()
PYEOF

# ── Write start script ─────────────────────────────────────
cat > "$SCRIPT_DIR/start.sh" <<STARTEOF
#!/usr/bin/env bash
set -euo pipefail
cd "\$(dirname "\${BASH_SOURCE[0]}")"
source .venv/bin/activate
export XOLO_TRUST_PROXY=${_TRUST_PROXY}
exec .venv/bin/python3 -m uvicorn server.main:app \\
  --host ${XOLO_HOST} \\
  --port ${XOLO_PORT} \\
  --ssl-keyfile server/certs/key.pem \\
  --ssl-certfile server/certs/cert.pem \\
  --log-level warning
STARTEOF
chmod +x "$SCRIPT_DIR/start.sh"

echo ""
echo -e "${MAG}${BLD}"
cat << 'BANNER'
  ╔═══════════════════════════════════════════════════════╗
  ║              XoloC2 — Installation Complete           ║
  ╚═══════════════════════════════════════════════════════╝
BANNER
echo -e "${RST}"
echo -e "  ${BLD}URL:${RST}       ${GRN}https://0.0.0.0:${XOLO_PORT}${RST}"
echo -e "  ${BLD}Username:${RST}  ${CYN}admin${RST}"
echo -e "  ${BLD}Password:${RST}  ${YLW}${ADMIN_PASS}${RST}"
echo ""
echo -e "  ${RED}⚠  Copia esta contraseña — NO se mostrará de nuevo!${RST}"
echo -e "  ${YLW}⚠  Deberás cambiarla obligatoriamente al iniciar sesión.${RST}"
echo ""
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  ${BLD}Iniciar C2:${RST}  ./start.sh"
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""
