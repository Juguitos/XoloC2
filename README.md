# XoloC2

A web-based Command & Control framework built for authorized penetration testing engagements.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

> **For authorized use only.** Only deploy against systems you have explicit written permission to test.

---

## Features

### Operator Panel
- **Dark web UI** — real-time dashboard powered by WebSockets
- **Session management** — view all active/inactive beacons with live status
- **Interactive terminal** — command-by-command shell with history (↑↓), CWD tracking
- **PTY shell** — full interactive pseudo-terminal via xterm.js (Linux beacons)
- **File upload** — stage files on the server, beacon pulls and writes them to target
- **File download / exfil** — download any file from the target to operator browser
- **Screenshot** — capture and preview target screen inline
- **Process list** — `ps` output formatted by platform
- **Kill process** — send SIGTERM/taskkill by PID
- **Session notes** — per-agent markdown notes
- **Export tasks** — export full command/output history as `.txt` or `.json`

### Beacon
- **Python 3 stdlib only** — no dependencies required on target
- **HTTPS polling** — configurable sleep + jitter
- **Multi-listener failover** — define primary + fallback C2 URLs
- **Persistence** — Windows Registry / Linux crontab
- **XOR+nonce payload encryption** — all beacon bodies encrypted, server decrypts transparently
- **Traffic camouflage** — randomized real browser User-Agents and Referer headers
- **Sandbox detection** — detects VMs, low CPU/RAM, sandbox usernames/hostnames, analysis tools, timing attacks
- **Process masquerade** — renames process to `[kworker/0:1]` on Linux via `prctl`
- **Linux ELF compile** — one-click PyInstaller compile from the panel

### Pivoting
- **SOCKS5 tunnel** — HTTP-tunnelled SOCKS5 proxy over beacon polling (no extra tools needed)
  - Start listener on any local port (default 1080)
  - Use with `proxychains`, Burp Suite, or browser proxy settings
  - Multi-channel concurrent TCP connections through beacon

### Infrastructure
- **Redirector config generator** — generates Apache / nginx / Caddy configs for traffic redirection
- **IP whitelist** — restrict panel access to specific public IPs (beacons always bypass)
- **WebSocket real-time events** — instant notifications on new agent check-in and task completion
- **Self-signed TLS** — HTTPS out of the box, RSA 4096, 10-year cert

### Security
- **JWT authentication** — 3-hour sessions with forced password change on first login
- **bcrypt password hashing**
- **IP whitelist middleware** — `/api/beacon/*` always exempt

---

## Quick Start

### Requirements
- Python 3.10+
- `openssl`

### Install

```bash
git clone https://github.com/Juguitos/XoloC2.git
cd XoloC2
bash install.sh
```

The installer will:
1. Prompt for the HTTPS port (default `8443`)
2. Create a Python virtual environment and install dependencies
3. Generate a self-signed TLS certificate
4. Bootstrap the database with a random `admin` password
5. Write a `start.sh` launch script

```
  URL:       https://0.0.0.0:8443
  Username:  admin
  Password:  <random — shown once>
```

> You will be required to change the password on first login.

### Start

```bash
./start.sh
```

### Non-interactive install

```bash
bash install.sh --port 443
bash install.sh --port 8443 --host 127.0.0.1
```

---

## Usage

### 1. Generate a Beacon

Go to **Generate Beacon** in the sidebar:
- Set your C2 listener URL(s)
- Configure sleep interval and jitter
- Choose evasion options
- Download `.py` or compile to Linux ELF

### 2. Deploy

```bash
# On target (Python required)
python3 beacon.py

# Or compiled binary
./beacon
```

### 3. Interact

- Click the session in the **Sessions** view
- Use the terminal to run commands
- Click **🖥 PTY Shell** for a full interactive shell (Linux only)
- Use **↑ Upload** to push files to the target

### 4. SOCKS5 Tunnel

In the session sidebar:
1. Set a local port (e.g. `1080`)
2. Click **▶ Start**
3. Configure `proxychains` or browser to use `SOCKS5 127.0.0.1:1080`
4. Browse internal network through the beacon

```bash
proxychains nmap -sT -Pn 192.168.1.0/24
```

---

## Architecture

```
XoloC2/
├── install.sh              # Installer
├── server/
│   ├── main.py             # FastAPI app, WebSocket endpoint, IP whitelist middleware
│   ├── database.py         # SQLAlchemy models (Agent, Task, User)
│   ├── auth.py             # JWT + bcrypt
│   ├── config.py           # Agent secret, settings
│   ├── websocket_manager.py
│   ├── socks5_server.py    # HTTP-tunnelled SOCKS5 proxy
│   ├── routers/
│   │   ├── auth_router.py      # Login, change password
│   │   ├── agents_router.py    # Agent CRUD, task queue, upload/exfil
│   │   ├── beacon_router.py    # Beacon checkin, result, file fetch
│   │   ├── pty_router.py       # PTY session management
│   │   ├── tunnel_router.py    # SOCKS5 tunnel endpoints
│   │   ├── info_router.py      # Agent secret, beacon compile
│   │   └── settings_router.py  # Password change, IP whitelist
│   └── templates/
│       └── dashboard.html  # Single-page app (vanilla JS)
```

---

## Beacon Commands

| Command | Description |
|---|---|
| `info` | Agent info (ID, OS, IP, user, PID, CWD) |
| `screenshot` | Capture and exfil screen |
| `ps` | List running processes |
| `kill <pid>` | Terminate process by PID |
| `download <path>` | Exfil file to operator |
| `sleep <seconds>` | Change check-in interval |
| `shell <cmd>` | Run shell command explicitly |
| `<any text>` | Executed as shell command directly |

---

## Disclaimer

XoloC2 is developed for **authorized penetration testing and security research only**.
Unauthorized use against systems without explicit written permission is illegal.
The authors assume no liability for misuse.
