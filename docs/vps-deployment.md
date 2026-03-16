# XoloC2 — VPS Deployment Guide

**[ [English](#english) | [Español](#español) ]**

---

<a name="english"></a>
# 🇬🇧 English — VPS Deployment with Domain

This guide covers deploying XoloC2 on a VPS with a custom domain, valid TLS certificate (Let's Encrypt), and nginx as a reverse proxy.

---

## Requirements

| Requirement | Minimum |
|---|---|
| VPS | 1 vCPU, 1 GB RAM, 10 GB disk |
| OS | Ubuntu 22.04 / Debian 12 |
| Domain | A domain or subdomain pointed at the VPS |
| Open ports | 80, 443 in the firewall |
| Python | 3.10+ (included in Ubuntu 22.04) |

> **Recommendation:** use a subdomain with a generic name (e.g. `updates.yourdomain.com`) to reduce C2 exposure.

---

## Step 1 — Prepare the VPS

Connect and update the system:

```bash
ssh root@<VPS_IP>
apt update && apt upgrade -y
apt install -y git nginx certbot python3-certbot-nginx python3 python3-venv openssl
```

Create a non-root user to run the C2:

```bash
adduser xolo
usermod -aG sudo xolo
su - xolo
```

---

## Step 2 — Point the Domain to the VPS

In your domain registrar's panel (Cloudflare, Namecheap, GoDaddy, etc.), create an **A record**:

```
Type:  A
Name:  c2          (or any subdomain, e.g.: updates)
Value: <VPS_PUBLIC_IP>
TTL:   300
```

Result: `c2.yourdomain.com` → `<VPS_IP>`

> Wait 5–10 minutes for DNS propagation before continuing.

Verify:
```bash
ping c2.yourdomain.com
# Should reply from your VPS IP
```

---

## Step 3 — Install XoloC2

```bash
cd /opt
sudo git clone https://github.com/Juguitos/XoloC2.git
sudo chown -R xolo:xolo /opt/XoloC2
cd /opt/XoloC2
bash install.sh --port 8443 --host 127.0.0.1
```

> Using `--host 127.0.0.1` ensures XoloC2 **only listens on localhost** — nginx handles all external traffic.

Write down the username and password printed by the installer.

---

## Step 4 — Configure nginx as Reverse Proxy

Create the nginx config file:

```bash
sudo nano /etc/nginx/sites-available/xoloc2
```

Paste the following (replace `c2.yourdomain.com`):

```nginx
server {
    listen 80;
    server_name c2.yourdomain.com;
    # Certbot will complete this block automatically
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/xoloc2 /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## Step 5 — Get a TLS Certificate with Let's Encrypt

```bash
sudo certbot --nginx -d c2.yourdomain.com
```

Certbot will ask for your email and whether to redirect HTTP → HTTPS. Choose **redirect (option 2)**.

After Certbot runs, edit the config to add the reverse proxy:

```bash
sudo nano /etc/nginx/sites-available/xoloc2
```

Replace the entire content with:

```nginx
server {
    listen 80;
    server_name c2.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name c2.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/c2.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/c2.yourdomain.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Max upload size
    client_max_body_size 50M;

    # WebSocket support
    location /ws {
        proxy_pass         https://127.0.0.1:8443;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_ssl_verify   off;
        proxy_read_timeout 3600s;
    }

    # Everything else → XoloC2
    location / {
        proxy_pass         https://127.0.0.1:8443;
        proxy_ssl_verify   off;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

Test and reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## Step 6 — Run XoloC2 as a systemd Service

Create the service file:

```bash
sudo nano /etc/systemd/system/xoloc2.service
```

```ini
[Unit]
Description=XoloC2 C2 Framework
After=network.target

[Service]
Type=simple
User=xolo
WorkingDirectory=/opt/XoloC2
ExecStart=/opt/XoloC2/start.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable xoloc2
sudo systemctl start xoloc2
sudo systemctl status xoloc2
```

---

## Step 7 — Verify the Deployment

Open in your browser:
```
https://c2.yourdomain.com
```

You should see the XoloC2 login page with a valid TLS certificate (green padlock).
Check that the **● WS** indicator in the dashboard turns green (WebSocket connected).

---

## Step 8 — Configure Beacons

When generating a beacon from the panel, use the public C2 URL:

```
https://c2.yourdomain.com
```

Do not use the raw IP or port 8443 — beacons connect through nginx on port 443.

---

## Step 9 — Firewall (Recommended)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

> Also enable the **IP Whitelist** under **Settings → IP Whitelist** in the panel for an extra layer of protection.

---

## Step 10 — Automatic Certificate Renewal

Certbot installs an automatic cron job. Verify it works:

```bash
sudo certbot renew --dry-run
```

---

## Port Summary

| Port | Protocol | Purpose |
|---|---|---|
| 22 | TCP | SSH to VPS |
| 80 | TCP | HTTP → redirects to HTTPS |
| 443 | TCP | HTTPS — panel + beacons (nginx) |
| 8443 | TCP | XoloC2 internal (localhost only) |

---

## Useful Commands

```bash
# Live logs
sudo journalctl -u xoloc2 -f

# Restart
sudo systemctl restart xoloc2

# Status
sudo systemctl status xoloc2

# Stop
sudo systemctl stop xoloc2
```

---

## Troubleshooting

**Panel does not load:**
```bash
sudo systemctl status xoloc2       # Is it running?
sudo nginx -t                       # Any nginx errors?
curl -k https://127.0.0.1:8443     # Does XoloC2 respond locally?
```

**WebSocket not connecting (● WS grey):**
- Verify the `location /ws` block in nginx has `proxy_http_version 1.1` and the `Upgrade` header
- Some VPS providers block WebSockets — contact support

**Beacon not connecting:**
- Verify the beacon URL is `https://c2.yourdomain.com` (no port)
- Verify port 443 is open: `sudo ufw status`
- Test from the VPS: `curl https://c2.yourdomain.com/api/beacon/checkin`

---
---

<a name="español"></a>
# 🇲🇽 Español — Despliegue en VPS con Dominio

Esta guía cubre el despliegue de XoloC2 en un VPS con dominio propio, certificado TLS válido (Let's Encrypt) y nginx como reverse proxy.

---

## Requisitos

| Requisito | Mínimo |
|---|---|
| VPS | 1 vCPU, 1 GB RAM, 10 GB disco |
| OS | Ubuntu 22.04 / Debian 12 |
| Dominio | Un dominio o subdominio apuntando al VPS |
| Puertos | 80 y 443 abiertos en el firewall |
| Python | 3.10+ (incluido en Ubuntu 22.04) |

> **Recomendación:** usa un subdominio con nombre genérico (ej: `updates.tudominio.com`) para reducir la exposición del C2.

---

## Paso 1 — Preparar el VPS

Conéctate y actualiza el sistema:

```bash
ssh root@<IP_VPS>
apt update && apt upgrade -y
apt install -y git nginx certbot python3-certbot-nginx python3 python3-venv openssl
```

Crea un usuario no-root para correr el C2:

```bash
adduser xolo
usermod -aG sudo xolo
su - xolo
```

---

## Paso 2 — Apuntar el Dominio al VPS

En el panel de tu registrador de dominio (Cloudflare, Namecheap, GoDaddy, etc.), crea un registro **tipo A**:

```
Tipo:   A
Nombre: c2          (o el subdominio que quieras, ej: updates)
Valor:  <IP_PÚBLICA_VPS>
TTL:    300
```

Resultado: `c2.tudominio.com` → `<IP_VPS>`

> Espera 5-10 minutos a que el DNS propague antes de continuar.

Verifica:
```bash
ping c2.tudominio.com
# Debe responder desde la IP de tu VPS
```

---

## Paso 3 — Instalar XoloC2

```bash
cd /opt
sudo git clone https://github.com/Juguitos/XoloC2.git
sudo chown -R xolo:xolo /opt/XoloC2
cd /opt/XoloC2
bash install.sh --port 8443 --host 127.0.0.1
```

> Usamos `--host 127.0.0.1` para que XoloC2 **solo escuche en localhost** — nginx se encarga de recibir el tráfico externo.

Anota el usuario y contraseña que muestra el instalador.

---

## Paso 4 — Configurar nginx como Reverse Proxy

Crea el archivo de configuración de nginx:

```bash
sudo nano /etc/nginx/sites-available/xoloc2
```

Pega lo siguiente (reemplaza `c2.tudominio.com`):

```nginx
server {
    listen 80;
    server_name c2.tudominio.com;
    # Certbot completará este bloque automáticamente
}
```

Activa el sitio:

```bash
sudo ln -s /etc/nginx/sites-available/xoloc2 /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## Paso 5 — Obtener Certificado TLS con Let's Encrypt

```bash
sudo certbot --nginx -d c2.tudominio.com
```

Certbot te preguntará tu email y si redirigir HTTP → HTTPS. Elige **redirigir (opción 2)**.

Después de que Certbot termine, edita la config para añadir el proxy inverso:

```bash
sudo nano /etc/nginx/sites-available/xoloc2
```

Reemplaza el contenido completo con:

```nginx
server {
    listen 80;
    server_name c2.tudominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name c2.tudominio.com;

    ssl_certificate     /etc/letsencrypt/live/c2.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/c2.tudominio.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Tamaño máximo de upload
    client_max_body_size 50M;

    # Soporte WebSocket
    location /ws {
        proxy_pass         https://127.0.0.1:8443;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_ssl_verify   off;
        proxy_read_timeout 3600s;
    }

    # Todo lo demás → XoloC2
    location / {
        proxy_pass         https://127.0.0.1:8443;
        proxy_ssl_verify   off;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

Verifica y recarga:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## Paso 6 — Correr XoloC2 como Servicio systemd

Crea el archivo de servicio:

```bash
sudo nano /etc/systemd/system/xoloc2.service
```

```ini
[Unit]
Description=XoloC2 C2 Framework
After=network.target

[Service]
Type=simple
User=xolo
WorkingDirectory=/opt/XoloC2
ExecStart=/opt/XoloC2/start.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Activa e inicia:

```bash
sudo systemctl daemon-reload
sudo systemctl enable xoloc2
sudo systemctl start xoloc2
sudo systemctl status xoloc2
```

---

## Paso 7 — Verificar el Despliegue

Abre en tu navegador:
```
https://c2.tudominio.com
```

Deberías ver la pantalla de login de XoloC2 con certificado TLS válido (candado verde).
Verifica que el indicador **● WS** en el dashboard se ponga verde (WebSocket conectado).

---

## Paso 8 — Configurar los Beacons

Al generar un beacon desde el panel, usa la URL pública del C2:

```
https://c2.tudominio.com
```

No uses la IP ni el puerto 8443 — los beacons entran por nginx en el puerto 443.

---

## Paso 9 — Firewall (Recomendado)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

> Además, activa la **IP Whitelist** en **Settings → IP Whitelist** del panel para una capa extra de protección.

---

## Paso 10 — Renovación Automática del Certificado

Certbot instala un cron automático. Verifica que funciona:

```bash
sudo certbot renew --dry-run
```

---

## Resumen de Puertos

| Puerto | Protocolo | Uso |
|---|---|---|
| 22 | TCP | SSH al VPS |
| 80 | TCP | HTTP → redirige a HTTPS |
| 443 | TCP | HTTPS — panel + beacons (nginx) |
| 8443 | TCP | XoloC2 interno (solo localhost) |

---

## Comandos Útiles

```bash
# Ver logs en tiempo real
sudo journalctl -u xoloc2 -f

# Reiniciar el C2
sudo systemctl restart xoloc2

# Ver estado
sudo systemctl status xoloc2

# Detener el C2
sudo systemctl stop xoloc2
```

---

## Solución de Problemas

**El panel no carga:**
```bash
sudo systemctl status xoloc2        # ¿Está corriendo?
sudo nginx -t                        # ¿nginx tiene errores?
curl -k https://127.0.0.1:8443      # ¿XoloC2 responde localmente?
```

**El WebSocket no conecta (● WS gris):**
- Verifica que el bloque `location /ws` en nginx tiene `proxy_http_version 1.1` y el header `Upgrade`
- Algunos proveedores de VPS bloquean WebSockets — contacta a soporte

**El beacon no conecta:**
- Verifica que la URL en el beacon es `https://c2.tudominio.com` (sin puerto)
- Verifica que el puerto 443 está abierto: `sudo ufw status`
- Prueba desde el VPS: `curl https://c2.tudominio.com/api/beacon/checkin`
