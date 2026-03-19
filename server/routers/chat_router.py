"""Operator real-time chat — persisted messages, broadcast via WebSocket."""
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, OperatorMessage, User
from auth import require_auth
from websocket_manager import manager as ws_manager

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendMessage(BaseModel):
    text: str


@router.get("/user-count")
def user_count(db: Session = Depends(get_db), _: User = Depends(require_auth)):
    return {"count": db.query(User).count()}


@router.get("")
def get_messages(db: Session = Depends(get_db), _: User = Depends(require_auth)):
    msgs = (
        db.query(OperatorMessage)
        .order_by(OperatorMessage.timestamp.asc())
        .limit(100)
        .all()
    )
    return [
        {
            "id":        m.id,
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

    msg = OperatorMessage(author=current_user.username, text=text)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    asyncio.create_task(ws_manager.broadcast({
        "type":      "chat_message",
        "id":        msg.id,
        "author":    msg.author,
        "text":      msg.text,
        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
    }))

    return {"ok": True}
