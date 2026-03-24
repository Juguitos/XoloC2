"""Operator real-time chat — persisted messages, scoped per session (agent_id)."""
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, OperatorMessage, User
from auth import require_auth
from websocket_manager import manager as ws_manager

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendMessage(BaseModel):
    text: str
    agent_id: str = ""


@router.get("/user-count")
def user_count(db: Session = Depends(get_db), _: User = Depends(require_auth)):
    return {"count": db.query(User).count()}


@router.get("")
def get_messages(
    agent_id: str = Query(default=""),
    db: Session = Depends(get_db),
    _: User = Depends(require_auth),
):
    msgs = (
        db.query(OperatorMessage)
        .filter(OperatorMessage.agent_id == agent_id)
        .order_by(OperatorMessage.timestamp.asc())
        .limit(100)
        .all()
    )
    return [
        {
            "id":        m.id,
            "agent_id":  m.agent_id,
            "author":    m.author,
            "text":      m.text,
            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
        }
        for m in msgs
    ]


@router.post("")
async def send_message(
    req: SendMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")
    if len(text) > 1000:
        raise HTTPException(status_code=400, detail="Message too long")

    msg = OperatorMessage(agent_id=req.agent_id, author=current_user.username, text=text)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    asyncio.create_task(ws_manager.broadcast({
        "type":      "chat_message",
        "agent_id":  msg.agent_id,
        "id":        msg.id,
        "author":    msg.author,
        "text":      msg.text,
        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
    }))

    return {"ok": True}
