# XoloC2

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**[ [English](#english) | [Español](#español) ]**

---

## Screenshots

<table>
  <tr>
    <td align="center"><b>Login</b></td>
    <td align="center"><b>Sessions</b></td>
  </tr>
  <tr>
    <td><img src="img/1.png" width="480"/></td>
    <td><img src="img/2.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>Generate Beacon</b></td>
    <td align="center"><b>Beacon Code Output</b></td>
  </tr>
  <tr>
    <td><img src="img/3.png" width="480"/></td>
    <td><img src="img/4.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>Session Shell + SOCKS5 Tunnel</b></td>
    <td align="center"><b>Command Execution</b></td>
  </tr>
  <tr>
    <td><img src="img/6.png" width="480"/></td>
    <td><img src="img/7.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>PTY Interactive Shell (sudo su → root)</b></td>
    <td align="center"><b>Screenshot Exfil (Windows agent)</b></td>
  </tr>
  <tr>
    <td><img src="img/8.png" width="480"/></td>
    <td><img src="img/9.png" width="480"/></td>
  </tr>
  <tr>
    <td align="center"><b>Redirector Config Generator</b></td>
    <td align="center"><b>Settings (Password + IP Whitelist)</b></td>
  </tr>
  <tr>
    <td><img src="img/5.png" width="480"/></td>
    <td><img src="img/11.png" width="480"/></td>
  </tr>
</table>

---

<a name="english"></a>
# 🇬🇧 English

> **For authorized use only.** Only deploy against systems you have explicit written permission to test.

## What is XoloC2?

XoloC2 is a web-based Command & Control framework built for authorized penetration testing engagements. It provides a clean dark-themed dashboard, a Python beacon that runs with no external dependencies, and a full set of post-exploitation capabilities.

---

## Features

### Operator Panel
- **Real-time dashboard** powered by WebSockets — instant agent check-in and task completion notifications
- **Session management** — view all active/inactive beacons with live online/offline status
- **Interactive terminal** — command-by-command shell with command history (↑↓) and CWD tracking
- **PTY shell** — full interactive pseudo-terminal via xterm.js (Linux beacons only)
- **File upload** — stage files on the server, beacon pulls and writes them to the target path
- **File download / exfil** — download any file from the target directly to the operator browser
- **Screenshot** — capture and preview target screen inline in the terminal
- **Process list** — cross-platform `ps` output
- **Kill process** — send SIGTERM / taskkill by PID
- **Session notes** — per-agent text notes
- **Export tasks** — full command/output history as `.txt` or `.json`
- **Redirector config generator** — generates Apache / nginx / Caddy configs for traffic redirection

### Beacon
- **Python 3 stdlib only** — no pip install required on target
- **HTTPS polling** — configurable sleep interval + jitter percentage
- **Multi-listener failover** — primary + fallback C2 URLs
- **Persistence** — Windows Registry (`HKCU\...\Run`) / Linux crontab (`@reboot`)
- **XOR + nonce payload encryption** — all beacon request bodies encrypted, server decrypts transparently
- **Traffic camouflage** — randomized real browser User-Agents and Referer headers
- **Sandbox detection** — detects VMs, low CPU/RAM, sandbox usernames/hostnames, analysis tools, timing attacks
- **Process masquerade** — renames process to `[kworker/0:1]` on Linux via `prctl`
- **Linux ELF compile** — one-click PyInstaller compile from the panel

### Pivoting
- **SOCKS5 tunnel** — HTTP-tunnelled SOCKS5 proxy multiplexed over beacon polling
  - No extra tools required on target
  - Start listener on any local port (default `1080`)
  - Use with `proxychains`, Burp Suite, Firefox, or any SOCKS5-aware tool
  - Supports multiple concurrent TCP channels

### Security
- **JWT authentication** — 3-hour sessions, forced password change on first login
- **bcrypt** password hashing
- **IP whitelist** — restrict panel access to specific public IPs (beacon endpoints always bypass)
- **Self-signed TLS** — HTTPS out of the box, RSA 4096, 10-year cert

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
  Password:  <random — shown once, must be changed on first login>
```

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
- Choose evasion options (traffic camouflage, sandbox detection, process masquerade, payload encryption)
- Download `.py` or compile to Linux ELF

### 2. Deploy on Target

```bash
python3 beacon.py
# or compiled binary
./beacon
```

### 3. Interact

- Click a session in **Sessions**
- Use the terminal to run commands
- Click **🖥 PTY Shell** for a full interactive shell (Linux only)
- Use **↑ Upload** to push files to the target

### 4. SOCKS5 Pivot

In the session sidebar → **SOCKS5 Tunnel**:
1. Set a local port (e.g. `1080`) → click **▶ Start**
2. Configure `proxychains` to use `socks5 127.0.0.1 1080`
3. Browse the internal network through the beacon

```bash
proxychains nmap -sT -Pn 192.168.1.0/24
```

---

## Architecture

```
XoloC2/
├── install.sh                  # Installer (interactive port prompt)
├── server/
│   ├── main.py                 # FastAPI app, WebSocket, IP whitelist middleware
│   ├── database.py             # SQLAlchemy models (Agent, Task, User)
│   ├── auth.py                 # JWT + bcrypt
│   ├── config.py               # Agent secret, app settings
│   ├── websocket_manager.py    # WebSocket broadcast manager
│   ├── socks5_server.py        # HTTP-tunnelled SOCKS5 proxy engine
│   ├── routers/
│   │   ├── auth_router.py      # Login, change password
│   │   ├── agents_router.py    # Agent CRUD, task queue, upload/exfil
│   │   ├── beacon_router.py    # Beacon checkin, result, file fetch, XOR decrypt
│   │   ├── pty_router.py       # PTY session management
│   │   ├── tunnel_router.py    # SOCKS5 tunnel beacon endpoints
│   │   ├── info_router.py      # Agent secret, beacon compile
│   │   └── settings_router.py  # Password change, IP whitelist
│   └── templates/
│       └── dashboard.html      # Single-page app (vanilla JS, no framework)
└── docs/
    └── vps-deployment.md       # VPS + domain deployment guide
```

---

## Beacon Commands

| Command | Description |
|---|---|
| `info` | Agent details (ID, OS, IP, user, PID, CWD) |
| `screenshot` | Capture and exfil screen |
| `ps` | List running processes |
| `kill <pid>` | Terminate process by PID |
| `download <path>` | Exfil file to operator |
| `sleep <seconds>` | Change check-in interval |
| `shell <cmd>` | Run shell command explicitly |
| `<any text>` | Executed as shell command directly |

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

XoloC2 es un framework de Command & Control basado en web, construido para pruebas de penetración autorizadas. Ofrece un dashboard con tema oscuro, un beacon Python que corre sin dependencias externas y un conjunto completo de capacidades post-explotación.

---

## Funcionalidades

### Panel del Operador
- **Dashboard en tiempo real** vía WebSockets — notificaciones instantáneas de check-in y resultados de tareas
- **Gestión de sesiones** — visualiza todos los beacons activos/inactivos con estado online/offline en vivo
- **Terminal interactiva** — shell comando a comando con historial (↑↓) y seguimiento del directorio actual
- **PTY shell** — pseudo-terminal interactiva completa vía xterm.js (solo beacons Linux)
- **Subida de archivos** — sube archivos al servidor, el beacon los descarga y escribe en el path destino
- **Descarga / exfiltración** — descarga cualquier archivo del target directamente al navegador del operador
- **Captura de pantalla** — captura y previsualiza la pantalla del target en la terminal
- **Lista de procesos** — salida `ps` multiplataforma
- **Terminar proceso** — envía SIGTERM / taskkill por PID
- **Notas de sesión** — notas de texto por agente
- **Exportar tareas** — historial completo de comandos/salidas en `.txt` o `.json`
- **Generador de config redirector** — genera configuraciones Apache / nginx / Caddy para redirección de tráfico

### Beacon
- **Solo stdlib de Python 3** — sin pip install requerido en el target
- **Polling HTTPS** — intervalo de sleep y jitter configurables
- **Failover multi-listener** — URLs C2 primaria + fallbacks
- **Persistencia** — Registro de Windows (`HKCU\...\Run`) / crontab Linux (`@reboot`)
- **Cifrado XOR + nonce** — todos los cuerpos de petición cifrados, el servidor descifra de forma transparente
- **Camuflaje de tráfico** — User-Agents y headers Referer reales de navegador, aleatorios
- **Detección de sandbox** — detecta VMs, CPU/RAM bajos, usernames/hostnames sospechosos, herramientas de análisis, ataques de timing
- **Mascarada de proceso** — renombra el proceso a `[kworker/0:1]` en Linux vía `prctl`
- **Compilar a ELF Linux** — compilación PyInstaller con un clic desde el panel

### Pivoting
- **Túnel SOCKS5** — proxy SOCKS5 tunelizado sobre HTTP, multiplexado sobre el polling del beacon
  - Sin herramientas adicionales requeridas en el target
  - Escucha en cualquier puerto local (por defecto `1080`)
  - Compatible con `proxychains`, Burp Suite, Firefox o cualquier herramienta que soporte SOCKS5
  - Múltiples canales TCP concurrentes

### Seguridad
- **Autenticación JWT** — sesiones de 3 horas, cambio de contraseña obligatorio en el primer login
- **Hash bcrypt** de contraseñas
- **Whitelist de IPs** — restringe el acceso al panel a IPs públicas específicas (los endpoints de beacon siempre pasan)
- **TLS autofirmado** — HTTPS listo para usar, RSA 4096, certificado de 10 años

---

## Inicio Rápido

### Requisitos
- Python 3.10+
- `openssl`

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

### Instalación no interactiva

```bash
bash install.sh --port 443
bash install.sh --port 8443 --host 127.0.0.1
```

---

## Uso

### 1. Generar un Beacon

Ve a **Generate Beacon** en la barra lateral:
- Configura la(s) URL(s) del listener C2
- Ajusta el intervalo de sleep y el jitter
- Selecciona opciones de evasión (camuflaje de tráfico, detección de sandbox, mascarada de proceso, cifrado)
- Descarga el `.py` o compila a ELF Linux

### 2. Desplegar en el Target

```bash
python3 beacon.py
# o el binario compilado
./beacon
```

### 3. Interactuar

- Haz clic en una sesión en **Sessions**
- Usa la terminal para ejecutar comandos
- Haz clic en **🖥 PTY Shell** para una shell interactiva completa (solo Linux)
- Usa **↑ Upload** para subir archivos al target

### 4. Pivoting con SOCKS5

En el sidebar de la sesión → **SOCKS5 Tunnel**:
1. Configura un puerto local (ej. `1080`) → clic en **▶ Start**
2. Configura `proxychains` para usar `socks5 127.0.0.1 1080`
3. Navega la red interna a través del beacon

```bash
proxychains nmap -sT -Pn 192.168.1.0/24
```

---

## Despliegue en VPS

Consulta [`docs/vps-deployment.md`](docs/vps-deployment.md) para la guía completa de despliegue con dominio propio, reverse proxy nginx y certificado Let's Encrypt válido.

---

## Aviso Legal

XoloC2 está desarrollado **exclusivamente para pruebas de penetración autorizadas e investigación de seguridad**.
El uso no autorizado contra sistemas sin permiso escrito explícito es ilegal.
Los autores no asumen ninguna responsabilidad por el mal uso.
