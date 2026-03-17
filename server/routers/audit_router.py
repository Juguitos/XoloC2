"""Audit log — admin-only view of security-relevant events."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db, AuditLog, User as DBUser
from auth import require_auth, User

router = APIRouter(prefix="/api/audit", tags=["audit"])


# ── Helper: write an audit entry ─────────────────────────────────────────────

def log_event(db: Session, actor: str, action: str, detail: str = "", ip: str = ""):
    """Insert one audit row. Safe to call inside any endpoint — swallows errors."""
    try:
        entry = AuditLog(actor=actor, action=action, detail=detail, ip=ip)
        db.add(entry)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def get_client_ip(request: Request) -> str:
    from config import TRUST_PROXY
    if TRUST_PROXY:
        return request.headers.get("X-Real-IP") or (request.client.host if request.client else "")
    return request.client.host if request.client else ""


# ── Admin-only dependency ─────────────────────────────────────────────────────

def require_admin(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    row = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not row or not row.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/logs")
def get_logs(
    limit: int = 300,
    action: Optional[str] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
    if action:
        q = q.filter(AuditLog.action == action)
    logs = q.limit(min(limit, 1000)).all()
    return [
        {
            "id": l.id,
            "actor": l.actor,
            "action": l.action,
            "detail": l.detail,
            "ip": l.ip,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        }
        for l in logs
    ]


@router.delete("/logs")
def clear_logs(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    db.query(AuditLog).delete()
    db.commit()
    return {"message": "Audit log cleared"}


@router.get("/is-admin")
def check_admin(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    row = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    return {"is_admin": bool(row and row.is_admin)}
