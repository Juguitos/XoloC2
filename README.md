<div align="center">

# XoloC2

**A web-based Command & Control framework for authorized penetration testing**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Java](https://img.shields.io/badge/Java-11+-ED8B00?logo=openjdk&logoColor=white)](https://openjdk.org)
[![Go](https://img.shields.io/badge/Go-1.21+-00ADD8?logo=go&logoColor=white)](https://go.dev)
[![PowerShell](https://img.shields.io/badge/PowerShell-5.1+-5391FE?logo=powershell&logoColor=white)](https://learn.microsoft.com/en-us/powershell/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**[ [English](#english) | [Español](#español) ]**

</div>

---

## Screenshots

<table>
  <tr>
    <td align="center"><b>Login</b></td>
    <td align="center"><b>MFA</b></td>
  </tr>
  <tr>
    <td><img src="img/login 01.png" width="480"/></td>
    <td><img src="img/login 02.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>Sessions Dashboard</b></td>
    <td align="center"><b>Session — Terminal & File Browser</b></td>
  </tr>
  <tr>
    <td><img src="img/dashboard 01.png" width="480"/></td>
    <td><img src="img/session 01.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>PTY Shell + SOCKS5 Tunnel</b></td>
    <td align="center"><b>Screenshot Exfil & Process List</b></td>
  </tr>
  <tr>
    <td><img src="img/session 02.png" width="480"/></td>
    <td><img src="img/session 03.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>Beacon Generator</b></td>
    <td align="center"><b>Generated Beacon Code</b></td>
  </tr>
  <tr>
    <td><img src="img/generate beacon 01.png" width="480"/></td>
    <td><img src="img/generate beacon 02.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>Stager — Encrypted Delivery</b></td>
    <td align="center"><b>Geographic Agent Map</b></td>
  </tr>
  <tr>
    <td><img src="img/stager 01.png" width="480"/></td>
    <td><img src="img/map 01.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>Network Topology</b></td>
    <td align="center"><b>Engagement Report</b></td>
  </tr>
  <tr>
    <td><img src="img/topology 01.png" width="480"/></td>
    <td><img src="img/report 01.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>Report Export (PDF / Markdown / HTML)</b></td>
  </tr>
  <tr>
    <td><img src="img/report 02.png" width="480"/></td>
  </tr>
</table>

---

<a name="english"></a>
# 🇬🇧 English

> **For authorized use only.** Only deploy against systems you have explicit written permission to test.

## What is XoloC2?

XoloC2 is a web-based Command & Control framework built for authorized penetration testing engagements. It features a dark-themed single-page dashboard, four beacon types (Python, Java, Go, PowerShell) that run with zero external dependencies on the target, encrypted stager delivery, and a full post-exploitation toolkit — all served from a single FastAPI process.

---

## Features

### Beacons

| Beacon | Platform | Dependencies | Evasion |
|--------|----------|-------------|---------|
| **Python 3** | Windows · Linux · macOS | None (stdlib only) | XOR strings, sandbox detection, process masquerade |
| **Java 11** | Windows · Linux · macOS | None (stdlib only) | XOR strings, sandbox detection |
| **Go 1.21** | Windows · Linux · macOS | None (stdlib only) | XOR strings, sandbox detection |
| **PowerShell 5.1** | Windows | None (built-in) | AMSI bypass · ETW disable · ScriptBlock logging disable · XOR strings |

All beacons share the same features unless noted:
- **HTTPS polling** — configurable sleep interval (1–300 s) and jitter % (0–80%)
- **Multi-listener failover** — primary C2 URL + unlimited fallback URLs
- **Unique XOR key per generation** — C2 URLs, agent secret, and sensitive strings are XOR-encoded with a fresh random key; two beacons from the same server have different static content
- **Per-request XOR + nonce payload encryption** — each request body is encrypted with a random nonce; server decrypts transparently
- **Server-side key delivery** — optional strongest encryption mode: the beacon fetches its own AES key from the server at runtime (key never embedded in the binary)
- **Kill date** — optional expiry; beacon self-destructs after the configured date
- **Heartbeat timeout** — beacon self-destructs if the C2 is unreachable for N days
- **Persistence** — Windows Registry Run key · Linux crontab `@reboot` · PowerShell Registry Run key
- **Traffic camouflage** — randomized real-browser User-Agents and Referer headers
- **Sandbox detection** — detects VMs, low CPU/RAM, sandbox usernames/hostnames, analysis tools, timing attacks
- **Process masquerade** — renames process to `[kworker/0:1]` on Linux via `prctl`
- **Background execution** — Windows: no-console process · Linux: double-fork daemon
- **CWD tracking** — current working directory persisted across check-ins, synced to the operator panel

### Stager — Encrypted Delivery

Generate a one-time token URL and serve the beacon through it. The payload is compressed (GZip) and encrypted (AES-256-CBC) at rest; the decryption key is embedded only in the delivery one-liner.

Execution methods served by a single stager token:

| Method | How it works |
|--------|-------------|
| **PS IEX** | PowerShell downloads the PS1 script and executes it in memory (`[ScriptBlock]::Create().Invoke()`) |
| **PS EncodedCommand** | Same as above, base64-encoded in UTF-16LE to bypass command-line logging |
| **HTA (mshta)** | VBScript wrapper that downloads and runs the Python beacon |
| **VBS** | Standalone `.vbs` that downloads and executes silently via `pythonw` |
| **Python (Linux/Mac)** | `urllib` + SSL bypass one-liner for `python3` / `python` |
| **curl / wget / sh** | Shell one-liners for Unix targets |
| **nc (raw TCP)** | Netcat fallback with no HTTP layer |
| **certutil** | Windows LOLBin download (cmd.exe and PowerShell variants) |

Stager tokens support max-use limits and expiry times. Revocable from the panel at any time.

### Operator Panel

- **Real-time dashboard** — WebSocket-powered; instant agent check-in and task completion notifications across all connected operators
- **Session management** — all active/inactive beacons with live online/offline status, external IP, OS, username, and geolocation flag
- **Interactive terminal** — command-by-command shell with history (↑↓) and CWD tracking on Windows and Linux
- **PTY shell** — full interactive pseudo-terminal via xterm.js (Linux beacons)
- **File browser** — navigate the target filesystem with back/forward history; click any file to download
- **File upload** — stage files on the server; the beacon pulls and writes them to the target path on next check-in
- **File download / exfil** — download any file from the target directly to the operator browser (binary-safe, 500 MB limit)
- **File search** — `find [path] <pattern>` built-in beacon command to search the target filesystem
- **Screenshot** — capture and preview the target screen inline in the terminal
- **Screenshot schedule** — `screenshot <N>` auto-captures every N minutes in the background; `screenshot 0` to stop
- **Process list** — cross-platform `ps` output
- **Kill process** — `kill <pid>` sends SIGTERM / taskkill
- **Session notes** — per-agent persistent text notes
- **Session tags** — label agents with custom tags for organization
- **Detection tracking** — mark a session as detected (with EDR/AV name) to track engagements
- **Export tasks** — clean command/output history as `.txt` or `.json` (internal protocol commands filtered automatically)
- **Operator chat** — real-time in-panel chat shared across all operators, per-session or global scope
- **Network topology** — vis.js graph of discovered internal network; run `neighbors` on any agent to map nearby hosts
- **Geographic map** — world map (Leaflet + CartoDB) showing agent locations resolved automatically from external IP at check-in

### Engagement Reports

- Generate PDF, Markdown, or HTML reports scoped to selected agents and date ranges
- Includes: agent summary, activity timeline, command/output history, exfiltrated files
- Configurable max output length per command entry
- Print-to-PDF directly from the browser

### Beacon Generator

- **One-click compile** — Python to Linux ELF (PyInstaller), Java to `.jar` (javac), Go cross-compilation (Windows/Linux/macOS), PowerShell `.ps1`
- **Output filename** — configurable; two beacons from different operations stay identifiable
- **Evasion options** — per-beacon toggles: traffic camouflage, sandbox detection, process masquerade, payload encryption, background execution
- **Features** — per-beacon toggles: file search, screenshot schedule

### Pivoting

- **SOCKS5 tunnel** — HTTP-tunnelled SOCKS5 proxy multiplexed over beacon polling
  - No extra tools required on the target
  - Start listener on any local port (default `1080`)
  - Compatible with `proxychains`, Burp Suite, Firefox, or any SOCKS5-aware tool
  - Supports multiple concurrent TCP channels

### Security & Operations

- **JWT authentication** — configurable session expiry, forced password change on first login
- **TOTP / MFA** — TOTP-based two-factor authentication (Google Authenticator / any TOTP app); QR code provisioning from the panel
- **Multi-operator** — create and delete operator accounts from Settings; admin role control
- **bcrypt** password hashing (min 12 characters enforced)
- **IP whitelist** — restrict panel access to specific IPs; beacon endpoints always bypass
- **Rate limiting** — 10 failed login attempts in 5 minutes triggers a 15-minute lockout
- **Agent secret rotation** — rotate the shared beacon secret from Settings; active beacons receive the new secret on next check-in and update automatically; the old secret stays valid until all beacons rotate
- **Audit log** — timestamped log of all security events (LOGIN, LOGIN_FAIL, TASK_SENT, FILE_UPLOAD, AGENT_DELETED, USER_CREATED, USER_DELETED, PASSWORD_CHANGED, SECRET_ROTATED); filterable and clearable
- **Webhook notifications** — Discord / Slack / any webhook alerts for configurable events (new agent, login, failed login, agent deleted, task sent)
- **Security headers** — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- **Redirector config generator** — generates ready-to-paste Apache / nginx / Caddy configs for C2 traffic redirection through a clean VPS
- **Bilingual UI** — full English / Spanish interface, togglable at runtime without reload
- **Timezone selector** — display all dates and logs in the operator's local timezone

---

## Quick Start

### Requirements

- Python 3.10+
- `openssl`
- *(optional)* `javac` / JDK 11+ for Java beacon compilation
- *(optional)* Go 1.21+ for Go beacon compilation

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
  Password:  <random — shown once, must be changed on first login>
```

### Start

```bash
./start.sh
```

### Run as a systemd service (recommended for production)

```bash
cat > /etc/systemd/system/xoloc2.service << 'EOF'
[Unit]
Description=XoloC2 C2 Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/XoloC2
Environment=XOLO_TRUST_PROXY=0
ExecStart=/opt/XoloC2/.venv/bin/python3 -m uvicorn server.main:app \
    --host 0.0.0.0 \
    --port 8443 \
    --ssl-keyfile server/certs/key.pem \
    --ssl-certfile server/certs/cert.pem \
    --log-level warning
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=xoloc2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xoloc2
systemctl start xoloc2
systemctl status xoloc2
```

```bash
journalctl -u xoloc2 -f
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
- Set your C2 listener URL(s) (primary + fallbacks)
- Select beacon type: Python · Java · Go · PowerShell
- Configure sleep interval, jitter %, optional kill date and heartbeat timeout
- Choose evasion and feature options
- Enable persistence if needed
- Download the source or compile to a binary directly from the panel

### 2. Deploy on Target

```bash
# Python
python3 beacon.py

# Compiled Linux binary
./beacon

# Java
java -jar beacon.jar

# Go binary (Windows)
beacon.exe

# PowerShell (in-memory, no disk)
powershell -nop -w hidden -File beacon.ps1
```

### 3. Interact

- Click a session in **Sessions**
- Use the terminal to run commands
- Click **🖥 PTY Shell** for a full interactive shell (Linux)
- Use **↑ Upload** to push files to the target
- Use the **File Browser** to navigate and exfil files

### 4. SOCKS5 Pivot

In the session panel → **SOCKS5 Tunnel**:
1. Set a local port (e.g. `1080`) → click **▶ Start**
2. Configure `proxychains` to use `socks5 127.0.0.1 1080`
3. Browse the internal network through the beacon

```bash
proxychains nmap -sT -Pn 192.168.1.0/24
```

### 5. Stager Delivery

In the session panel → **🎣 Stager** (or from the Stager section in the sidebar):
1. Paste the beacon code, set max uses and expiry
2. Click **Create** — a token URL is generated
3. Copy any one-liner from the list and run it on the target

---

## Beacon Commands

| Command | Description |
|---------|-------------|
| `info` | Agent details (ID, OS, IP, user, PID, CWD) |
| `screenshot` | Capture and exfil the target screen |
| `screenshot <N>` | Auto-capture every N minutes (`0` to stop) |
| `ps` | List running processes |
| `kill <pid>` | Terminate a process by PID |
| `download <path>` | Exfil a file to the operator browser |
| `find [path] <pattern>` | Search files on the target filesystem |
| `sleep <seconds>` | Change the check-in interval |
| `cd <path>` | Change working directory |
| `neighbors` | Discover hosts on the local network (populates Topology) |
| `shell <cmd>` | Run a shell command explicitly |
| `<any text>` | Executed directly as a shell command |

---

## Architecture

```
XoloC2/
├── install.sh                   # Installer (interactive or --port / --host flags)
├── server/
│   ├── main.py                  # FastAPI app, WebSocket, security headers, IP whitelist middleware
│   ├── database.py              # SQLAlchemy models + auto-migration (User, Agent, Task, AuditLog, StagerToken, BeaconKey, OperatorMessage)
│   ├── auth.py                  # JWT + bcrypt + TOTP
│   ├── config.py                # Agent secret rotation, JWT expiry, trust-proxy flag
│   ├── websocket_manager.py     # WebSocket broadcast manager (real-time sync across operators)
│   ├── socks5_server.py         # HTTP-tunnelled SOCKS5 proxy engine
│   ├── routers/
│   │   ├── auth_router.py       # Login (JWT + MFA), password change, rate limiting
│   │   ├── agents_router.py     # Agent CRUD, task queue, file upload/exfil, tags, notes, reports
│   │   ├── beacon_router.py     # Checkin (geo lookup), result submit, file fetch, XOR decrypt, secret rotation
│   │   ├── stager_router.py     # Stager token CRUD, AES-256-CBC encrypted blob, PS/HTA/VBS delivery endpoints
│   │   ├── pty_router.py        # PTY session management + WebSocket streaming
│   │   ├── tunnel_router.py     # SOCKS5 tunnel beacon endpoints
│   │   ├── topology_router.py   # Network topology graph (neighbors discovery)
│   │   ├── chat_router.py       # Operator real-time chat (WebSocket + DB persistence)
│   │   ├── info_router.py       # Agent secret, beacon compilation (Python/Java/Go)
│   │   ├── settings_router.py   # Password, IP whitelist, MFA setup/disable, user management
│   │   ├── audit_router.py      # Audit log (read, filter, clear)
│   │   └── webhook_router.py    # Webhook config + async dispatch
│   └── templates/
│       └── dashboard.html       # Single-page app (vanilla JS, no framework, EN/ES i18n)
└── docs/
    └── vps-deployment.md        # VPS + domain deployment guide
```

---

## Deployment on VPS

See [`docs/vps-deployment.md`](docs/vps-deployment.md) for a full guide on deploying with a domain, nginx reverse proxy, and a valid Let's Encrypt certificate.

---

## Disclaimer

XoloC2 is developed for **authorized penetration testing and security research only**.  
Unauthorized use against systems without explicit written permission is illegal.  
The authors assume no liability for misuse.

---
---

<a name="español"></a>
# 🇲🇽 Español

> **Solo para uso autorizado.** Únicamente despliega contra sistemas para los que tengas permiso escrito explícito.

## ¿Qué es XoloC2?

XoloC2 es un framework de Command & Control basado en web, construido para pruebas de penetración autorizadas. Cuenta con un dashboard de tema oscuro en una sola página, cuatro tipos de beacon (Python, Java, Go, PowerShell) que corren sin dependencias externas en el target, entrega cifrada mediante stager, y un conjunto completo de herramientas post-explotación — todo servido desde un único proceso FastAPI.

---

## Funcionalidades

### Beacons

| Beacon | Plataforma | Dependencias | Evasión |
|--------|-----------|-------------|---------|
| **Python 3** | Windows · Linux · macOS | Ninguna (solo stdlib) | XOR strings, detección sandbox, mascarada de proceso |
| **Java 11** | Windows · Linux · macOS | Ninguna (solo stdlib) | XOR strings, detección sandbox |
| **Go 1.21** | Windows · Linux · macOS | Ninguna (solo stdlib) | XOR strings, detección sandbox |
| **PowerShell 5.1** | Windows | Ninguna (integrado en Windows) | Bypass AMSI · Desactivar ETW · Desactivar ScriptBlock logging · XOR strings |

Todos los beacons comparten estas características salvo que se indique lo contrario:
- **Polling HTTPS** — intervalo de sleep (1–300 s) y jitter % (0–80%) configurables
- **Failover multi-listener** — URL C2 primaria + fallbacks ilimitados
- **Clave XOR única por generación** — URLs del C2, secreto del agente y strings sensibles se cifran XOR con una clave aleatoria nueva cada vez
- **Cifrado XOR + nonce por petición** — cada body de petición se cifra con un nonce aleatorio; el servidor descifra de forma transparente
- **Entrega de clave desde el servidor** — modo de cifrado más fuerte opcional: el beacon obtiene su propia clave AES del servidor en tiempo de ejecución
- **Kill date** — expiración opcional; el beacon se autodestruye al llegar la fecha configurada
- **Heartbeat timeout** — el beacon se autodestruye si el C2 es inalcanzable durante N días
- **Persistencia** — Registro de Windows Run key · Linux crontab `@reboot` · PS Registry Run key
- **Camuflaje de tráfico** — User-Agents y headers Referer reales de navegador, aleatorios
- **Detección de sandbox** — detecta VMs, CPU/RAM bajos, usernames/hostnames sospechosos, herramientas de análisis, timing attacks
- **Mascarada de proceso** — renombra el proceso a `[kworker/0:1]` en Linux via `prctl`
- **Ejecución en segundo plano** — Windows: proceso sin consola · Linux: daemon double-fork
- **Seguimiento del CWD** — directorio actual persistido entre check-ins, sincronizado al panel

### Stager — Entrega Cifrada

Genera una URL de token de un solo uso y sirve el beacon a través de ella. El payload se comprime (GZip) y cifra (AES-256-CBC) en reposo; la clave de descifrado solo se incluye en el one-liner de entrega.

Métodos de ejecución servidos por un único token de stager:

| Método | Cómo funciona |
|--------|--------------|
| **PS IEX** | PowerShell descarga el script PS1 y lo ejecuta en memoria (`[ScriptBlock]::Create().Invoke()`) |
| **PS EncodedCommand** | Igual que IEX pero codificado en base64 UTF-16LE para evadir logging de línea de comandos |
| **HTA (mshta)** | Wrapper VBScript que descarga y ejecuta el beacon Python |
| **VBS** | Archivo `.vbs` independiente que descarga y ejecuta en silencio via `pythonw` |
| **Python (Linux/Mac)** | One-liner `urllib` + bypass SSL para `python3` / `python` |
| **curl / wget / sh** | One-liners de shell para targets Unix |
| **nc (TCP raw)** | Fallback netcat sin capa HTTP |
| **certutil** | LOLBin de Windows (cmd.exe y PowerShell) |

Los tokens de stager soportan límite de usos y tiempo de expiración. Revocables desde el panel en cualquier momento.

### Panel del Operador

- **Dashboard en tiempo real** — WebSockets; notificaciones instantáneas de check-in y resultados de tareas entre todos los operadores conectados
- **Gestión de sesiones** — todos los beacons activos/inactivos con estado online/offline, IP externa, SO, usuario y bandera de geolocalización
- **Terminal interactiva** — shell comando a comando con historial (↑↓) y seguimiento del CWD en Windows y Linux
- **PTY shell** — pseudo-terminal interactiva completa vía xterm.js (beacons Linux)
- **Explorador de archivos** — navega el sistema de archivos del target con historial atrás/adelante; clic para descargar
- **Subida de archivos** — sube archivos al servidor; el beacon los descarga y escribe en la ruta destino en el siguiente check-in
- **Descarga / exfiltración** — descarga cualquier archivo del target directamente al navegador (compatible con binarios, límite 500 MB)
- **Búsqueda de archivos** — comando `find [ruta] <patrón>` integrado en el beacon para buscar en el sistema de archivos del target
- **Captura de pantalla** — captura y previsualiza la pantalla del target en la terminal
- **Screenshot automático** — `screenshot <N>` captura automáticamente cada N minutos en background; `screenshot 0` para detener
- **Lista de procesos** — salida `ps` multiplataforma
- **Terminar proceso** — `kill <pid>` envía SIGTERM / taskkill
- **Notas de sesión** — notas de texto persistentes por agente
- **Tags de sesión** — etiqueta agentes con tags personalizados
- **Seguimiento de detección** — marca una sesión como detectada (con nombre del EDR/AV) para documentar el engagement
- **Exportar tareas** — historial limpio de comandos/salidas en `.txt` o `.json`
- **Chat de operadores** — chat en tiempo real compartido entre todos los operadores, con scope por sesión o global
- **Topología de red** — grafo vis.js de la red interna descubierta; ejecuta `neighbors` en cualquier agente para mapear hosts vecinos
- **Mapa geográfico** — mapa mundial (Leaflet + CartoDB) que muestra la ubicación de los agentes resuelta automáticamente desde su IP externa al hacer check-in

### Reportes de Engagement

- Genera reportes en PDF, Markdown o HTML limitados a los agentes y rangos de fecha seleccionados
- Incluye: resumen del agente, línea de tiempo de actividad, historial de comandos/salidas, archivos exfiltrados
- Longitud máxima de output por entrada configurable
- Impresión a PDF directamente desde el navegador

### Generador de Beacon

- **Compilación con un clic** — Python a ELF Linux (PyInstaller), Java a `.jar` (javac), Go compilación cruzada (Windows/Linux/macOS), PowerShell `.ps1`
- **Nombre de archivo personalizable** — configurable; dos beacons de operaciones distintas se mantienen identificables
- **Opciones de evasión** — toggles por beacon: camuflaje de tráfico, detección de sandbox, mascarada de proceso, cifrado de payload, ejecución en segundo plano
- **Features** — toggles por beacon: búsqueda de archivos, screenshot automático

### Pivoting

- **Túnel SOCKS5** — proxy SOCKS5 tunelizado sobre HTTP, multiplexado sobre el polling del beacon
  - Sin herramientas adicionales en el target
  - Escucha en cualquier puerto local (por defecto `1080`)
  - Compatible con `proxychains`, Burp Suite, Firefox o cualquier herramienta SOCKS5
  - Múltiples canales TCP concurrentes

### Seguridad y Operaciones

- **Autenticación JWT** — expiración configurable, cambio de contraseña obligatorio en el primer login
- **TOTP / MFA** — autenticación de dos factores con TOTP (Google Authenticator / cualquier app TOTP); aprovisionamiento con QR desde el panel
- **Multi-operador** — crea y elimina cuentas desde Settings; control de rol admin
- **Hash bcrypt** de contraseñas (mínimo 12 caracteres)
- **Whitelist de IPs** — restringe el acceso al panel a IPs específicas; endpoints del beacon siempre pasan
- **Rate limiting** — 10 intentos fallidos en 5 minutos activa bloqueo de 15 minutos
- **Rotación de agent secret** — rota el secreto compartido desde Settings; los beacons activos reciben el nuevo secreto en el siguiente check-in y se actualizan automáticamente; el secreto viejo sigue válido hasta que todos roten
- **Registro de auditoría** — log con timestamps de todos los eventos de seguridad; filtrable y borrable
- **Notificaciones webhook** — alertas Discord / Slack / cualquier webhook para eventos configurables
- **Headers de seguridad** — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- **Generador de config redirector** — genera configuraciones listas para Apache / nginx / Caddy para redirección de tráfico C2 a través de un VPS limpio
- **UI bilingüe** — interfaz completa en inglés / español, cambiable en tiempo de ejecución sin recargar
- **Selector de zona horaria** — muestra todas las fechas y logs en la zona horaria del operador

---

## Inicio Rápido

### Requisitos

- Python 3.10+
- `openssl`
- *(opcional)* JDK 11+ para compilar beacons Java
- *(opcional)* Go 1.21+ para compilar beacons Go

### Instalación

```bash
git clone https://github.com/Juguitos/XoloC2.git
cd XoloC2
bash install.sh
```

El instalador:
1. Preguntará el puerto HTTPS (por defecto `8443`)
2. Crea un entorno virtual Python e instala dependencias
3. Genera un certificado TLS autofirmado
4. Inicializa la base de datos con una contraseña `admin` aleatoria
5. Escribe el script `start.sh` de arranque

```
  URL:       https://0.0.0.0:8443
  Usuario:   admin
  Contraseña: <aleatoria — se muestra una sola vez, debes cambiarla>
```

### Iniciar

```bash
./start.sh
```

### Ejecutar como servicio systemd (recomendado en producción)

```bash
cat > /etc/systemd/system/xoloc2.service << 'EOF'
[Unit]
Description=XoloC2 C2 Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/XoloC2
Environment=XOLO_TRUST_PROXY=0
ExecStart=/opt/XoloC2/.venv/bin/python3 -m uvicorn server.main:app \
    --host 0.0.0.0 \
    --port 8443 \
    --ssl-keyfile server/certs/key.pem \
    --ssl-certfile server/certs/cert.pem \
    --log-level warning
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=xoloc2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xoloc2
systemctl start xoloc2
systemctl status xoloc2
```

```bash
journalctl -u xoloc2 -f
```

### Instalación no interactiva

```bash
bash install.sh --port 443
bash install.sh --port 8443 --host 127.0.0.1
```

---

## Uso

### 1. Generar un Beacon

Ve a **Generate Beacon** en la barra lateral:
- Configura la(s) URL(s) del listener C2 (primaria + fallbacks)
- Selecciona el tipo de beacon: Python · Java · Go · PowerShell
- Ajusta sleep, jitter, kill date y heartbeat timeout opcionales
- Elige opciones de evasión y features
- Activa persistencia si es necesario
- Descarga el fuente o compila a binario directamente desde el panel

### 2. Desplegar en el Target

```bash
# Python
python3 beacon.py

# Binario Linux compilado
./beacon

# Java
java -jar beacon.jar

# Go (Windows)
beacon.exe

# PowerShell (en memoria, sin escritura a disco)
powershell -nop -w hidden -File beacon.ps1
```

### 3. Interactuar

- Haz clic en una sesión en **Sessions**
- Usa la terminal para ejecutar comandos
- Haz clic en **🖥 PTY Shell** para shell interactiva completa (Linux)
- Usa **↑ Upload** para subir archivos al target
- Usa el **Explorador de archivos** para navegar y exfiltrar archivos

### 4. Pivoting con SOCKS5

En el panel de sesión → **SOCKS5 Tunnel**:
1. Configura un puerto local (ej. `1080`) → clic en **▶ Start**
2. Configura `proxychains` para usar `socks5 127.0.0.1 1080`
3. Navega la red interna a través del beacon

```bash
proxychains nmap -sT -Pn 192.168.1.0/24
```

### 5. Entrega por Stager

En el panel de sesión → **🎣 Stager** (o desde la sección Stager en el sidebar):
1. Pega el código del beacon, configura máx. usos y expiración
2. Clic en **Crear** — se genera una URL de token
3. Copia cualquier one-liner de la lista y ejecútalo en el target

---

## Comandos del Beacon

| Comando | Descripción |
|---------|-------------|
| `info` | Detalles del agente (ID, SO, IP, usuario, PID, CWD) |
| `screenshot` | Captura y exfiltra la pantalla del target |
| `screenshot <N>` | Captura automática cada N minutos (`0` para detener) |
| `ps` | Lista los procesos en ejecución |
| `kill <pid>` | Termina un proceso por PID |
| `download <ruta>` | Exfiltra un archivo al navegador del operador |
| `find [ruta] <patrón>` | Busca archivos en el sistema de archivos del target |
| `sleep <segundos>` | Cambia el intervalo de check-in |
| `cd <ruta>` | Cambia el directorio de trabajo |
| `neighbors` | Descubre hosts en la red local (pobla Topología) |
| `shell <cmd>` | Ejecuta un comando de shell explícitamente |
| `<cualquier texto>` | Se ejecuta directamente como comando de shell |

---

## Arquitectura

```
XoloC2/
├── install.sh                   # Instalador (interactivo o con --port / --host)
├── server/
│   ├── main.py                  # App FastAPI, WebSocket, headers de seguridad, middleware whitelist
│   ├── database.py              # Modelos SQLAlchemy + auto-migración (User, Agent, Task, AuditLog, StagerToken, BeaconKey, OperatorMessage)
│   ├── auth.py                  # JWT + bcrypt + TOTP
│   ├── config.py                # Rotación de agent secret, expiración JWT, flag trust-proxy
│   ├── websocket_manager.py     # Gestor de broadcast WebSocket (sync en tiempo real entre operadores)
│   ├── socks5_server.py         # Motor de proxy SOCKS5 tunelizado sobre HTTP
│   ├── routers/
│   │   ├── auth_router.py       # Login (JWT + MFA), cambio de contraseña, rate limiting
│   │   ├── agents_router.py     # CRUD de agentes, cola de tareas, upload/exfil, tags, notas, reportes
│   │   ├── beacon_router.py     # Checkin (geo lookup), envío de resultados, fetch archivos, descifrado XOR, rotación de secreto
│   │   ├── stager_router.py     # CRUD de tokens stager, blob cifrado AES-256-CBC, endpoints PS/HTA/VBS
│   │   ├── pty_router.py        # Gestión de sesiones PTY + streaming WebSocket
│   │   ├── tunnel_router.py     # Endpoints del beacon para el túnel SOCKS5
│   │   ├── topology_router.py   # Grafo de topología de red (descubrimiento de vecinos)
│   │   ├── chat_router.py       # Chat en tiempo real entre operadores (WebSocket + persistencia en DB)
│   │   ├── info_router.py       # Agent secret, compilación de beacon (Python/Java/Go)
│   │   ├── settings_router.py   # Contraseña, whitelist, MFA setup/desactivar, gestión de usuarios
│   │   ├── audit_router.py      # Registro de auditoría (leer, filtrar, borrar)
│   │   └── webhook_router.py    # Config de webhook + despacho asíncrono
│   └── templates/
│       └── dashboard.html       # Single-page app (vanilla JS, sin framework, i18n EN/ES)
└── docs/
    └── vps-deployment.md        # Guía de despliegue en VPS con dominio propio
```

---

## Despliegue en VPS

Consulta [`docs/vps-deployment.md`](docs/vps-deployment.md) para la guía completa de despliegue con dominio propio, reverse proxy nginx y certificado Let's Encrypt válido.

---

## Aviso Legal

XoloC2 está desarrollado **exclusivamente para pruebas de penetración autorizadas e investigación de seguridad**.  
El uso no autorizado contra sistemas sin permiso escrito explícito es ilegal.  
Los autores no asumen ninguna responsabilidad por el mal uso.
