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

# ── TLS certificate ────────────────────────────────────────
mkdir -p "$CERT_DIR"
CERT="$CERT_DIR/cert.pem"
KEY="$CERT_DIR/key.pem"

if [[ ! -f "$CERT" ]] || [[ ! -f "$KEY" ]]; then
  echo -e "${YLW}[*] Generating self-signed TLS certificate (RSA 4096, 10 years)...${RST}"
  openssl req -x509 -newkey rsa:4096 -keyout "$KEY" -out "$CERT" \
    -days 3650 -nodes -subj "/CN=xolo-c2/O=XoloC2/C=MX" \
    -addext "subjectAltName=IP:127.0.0.1,IP:0.0.0.0" 2>/dev/null
  chmod 600 "$KEY"
  echo -e "${GRN}[✓] TLS certificate generated${RST}"
else
  echo -e "${GRN}[✓] TLS certificate already exists${RST}"
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
