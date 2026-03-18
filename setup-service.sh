#!/usr/bin/env bash
# ============================================================
#  XoloC2 — systemd service installer
#  Reads start.sh to auto-detect port, host and proxy config.
#  Usage: sudo bash setup-service.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
CYN='\033[0;36m'
MAG='\033[0;35m'
BLD='\033[1m'
RST='\033[0m'

SERVICE_NAME="xoloc2"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START_SH="$SCRIPT_DIR/start.sh"

echo ""
echo -e "${MAG}${BLD}"
cat << 'LOGO'
██╗  ██╗ ██████╗ ██╗      ██████╗  ██████╗██████╗
╚██╗██╔╝██╔═══██╗██║     ██╔═══██╗██╔════╝╚════██╗
 ╚███╔╝ ██║   ██║██║     ██║   ██║██║      █████╔╝
 ██╔██╗ ██║   ██║██║     ██║   ██║██║     ██╔═══╝
██╔╝ ██╗╚██████╔╝███████╗╚██████╔╝╚██████╗███████╗
╚═╝  ╚═╝ ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝╚══════╝
          systemd Service Installer
LOGO
echo -e "${RST}"
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"

# ── Root check ───────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  echo -e "${RED}[!] This script must be run as root (sudo bash setup-service.sh)${RST}"
  exit 1
fi

# ── start.sh check ───────────────────────────────────────────
if [[ ! -f "$START_SH" ]]; then
  echo -e "${RED}[!] start.sh not found at $START_SH${RST}"
  echo -e "${YLW}    Run install.sh first.${RST}"
  exit 1
fi

# ── Parse config from start.sh ───────────────────────────────
XOLO_HOST=$(grep -oP '(?<=--host )\S+' "$START_SH" || echo "0.0.0.0")
XOLO_PORT=$(grep -oP '(?<=--port )\S+' "$START_SH" || echo "8443")
TRUST_PROXY=$(grep -oP '(?<=XOLO_TRUST_PROXY=)\S+' "$START_SH" || echo "0")
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"
KEY_FILE="$SCRIPT_DIR/server/certs/key.pem"
CERT_FILE="$SCRIPT_DIR/server/certs/cert.pem"

echo -e "  ${BLD}Install dir:${RST}   ${CYN}${SCRIPT_DIR}${RST}"
echo -e "  ${BLD}Listen:${RST}        ${CYN}${XOLO_HOST}:${XOLO_PORT}${RST}"
echo -e "  ${BLD}Trust proxy:${RST}   ${CYN}${TRUST_PROXY}${RST}"
echo -e "  ${BLD}Service file:${RST}  ${CYN}${SERVICE_FILE}${RST}"
echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

# ── Confirm if service already exists ────────────────────────
if systemctl list-unit-files "${SERVICE_NAME}.service" &>/dev/null \
   && systemctl list-unit-files "${SERVICE_NAME}.service" | grep -q "${SERVICE_NAME}"; then
  echo -e "${YLW}[!] Service '${SERVICE_NAME}' already exists.${RST}"
  read -rp "$(echo -e "  Overwrite? [${YLW}y/N${RST}]: ")" _CONFIRM
  _CONFIRM="${_CONFIRM:-N}"
  if [[ ! "$_CONFIRM" =~ ^[yY]$ ]]; then
    echo -e "${RED}[!] Aborted.${RST}"
    exit 0
  fi
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
fi

# ── Write service file ────────────────────────────────────────
echo -e "${YLW}[*] Writing ${SERVICE_FILE}...${RST}"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=XoloC2 C2 Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${SCRIPT_DIR}
Environment=XOLO_TRUST_PROXY=${TRUST_PROXY}
ExecStart=${VENV_PYTHON} -m uvicorn server.main:app \\
    --host ${XOLO_HOST} \\
    --port ${XOLO_PORT} \\
    --ssl-keyfile ${KEY_FILE} \\
    --ssl-certfile ${CERT_FILE} \\
    --log-level warning
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GRN}[✓] Service file written${RST}"

# ── Reload, enable, start ─────────────────────────────────────
echo -e "${YLW}[*] Reloading systemd...${RST}"
systemctl daemon-reload

echo -e "${YLW}[*] Enabling service (start on boot)...${RST}"
systemctl enable "${SERVICE_NAME}"

echo -e "${YLW}[*] Starting service...${RST}"
systemctl start "${SERVICE_NAME}"

sleep 1

# ── Status ────────────────────────────────────────────────────
if systemctl is-active --quiet "${SERVICE_NAME}"; then
  echo ""
  echo -e "${MAG}${BLD}"
  cat << 'BANNER'
  ╔═══════════════════════════════════════════════════════╗
  ║            XoloC2 — Service Active ✓                  ║
  ╚═══════════════════════════════════════════════════════╝
BANNER
  echo -e "${RST}"
  echo -e "  ${BLD}Status:${RST}  ${GRN}running${RST}"
  echo -e "  ${BLD}URL:${RST}     ${GRN}https://${XOLO_HOST}:${XOLO_PORT}${RST}"
  echo ""
  echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
  echo -e "  ${BLD}View logs:${RST}    journalctl -u ${SERVICE_NAME} -f"
  echo -e "  ${BLD}Stop:${RST}         systemctl stop ${SERVICE_NAME}"
  echo -e "  ${BLD}Restart:${RST}      systemctl restart ${SERVICE_NAME}"
  echo -e "  ${BLD}Disable:${RST}      systemctl disable ${SERVICE_NAME}"
  echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
  echo ""
else
  echo ""
  echo -e "${RED}[!] Service failed to start. Check logs:${RST}"
  echo -e "    journalctl -u ${SERVICE_NAME} -n 30 --no-pager"
  echo ""
  systemctl status "${SERVICE_NAME}" --no-pager || true
  exit 1
fi
