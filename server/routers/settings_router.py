from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import json
import pyotp
from sqlalchemy.orm import Session
from database import get_db, User as DBUser
from auth import require_auth, User, hash_password
from routers.audit_router import log_event

router = APIRouter(prefix="/api/settings", tags=["settings"])

_WHITELIST_FILE = Path(__file__).parent.parent / "allowed_ips.json"


class IPEntry(BaseModel):
    name: str
    ip: str


class IPWhitelistConfig(BaseModel):
    enabled: bool
    entries: List[IPEntry]


def load_whitelist() -> dict:
    if _WHITELIST_FILE.exists():
        try:
            return json.loads(_WHITELIST_FILE.read_text())
        except Exception:
            pass
    return {"enabled": False, "entries": []}


def save_whitelist(data: dict):
    _WHITELIST_FILE.write_text(json.dumps(data, indent=2))


@router.get("/ipwhitelist")
def get_ipwhitelist(_: User = Depends(require_auth)):
    return load_whitelist()


@router.post("/ipwhitelist")
def set_ipwhitelist(req: IPWhitelistConfig, _: User = Depends(require_auth)):
    data = {
        "enabled": req.enabled,
        "entries": [{"name": e.name, "ip": e.ip} for e in req.entries],
    }
    save_whitelist(data)
    return {"message": "Saved"}


@router.get("/myip")
def get_my_ip(request: Request, _: User = Depends(require_auth)):
    xff = request.headers.get("X-Forwarded-For", "")
    ip = (
        request.headers.get("X-Real-IP")
        or (xff.split(",")[0].strip() if xff else None)
        or (request.client.host if request.client else "unknown")
    )
    return {"ip": ip or "unknown"}


# ── MFA ──────────────────────────────────────────────────────────────────────

@router.get("/mfa/status")
def mfa_status(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    return {"enabled": bool(user and user.totp_enabled)}


@router.post("/mfa/setup")
def mfa_setup(current_user: User = Depends(require_auth)):
    """Generate a new TOTP secret and return the provisioning URI.
    The secret is NOT saved yet — call /mfa/enable with the code to confirm."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.username, issuer_name="XoloC2")
    return {"secret": secret, "uri": uri}


class MFAEnableRequest(BaseModel):
    secret: str
    code: str


@router.post("/mfa/enable")
def mfa_enable(req: MFAEnableRequest, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Verify the TOTP code against the provided secret, then persist and enable MFA."""
    totp = pyotp.TOTP(req.secret)
    if not totp.verify(req.code.strip(), valid_window=1):
        raise HTTPException(status_code=400, detail="Código MFA incorrecto")
    user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    user.totp_secret = req.secret
    user.totp_enabled = True
    db.commit()
    return {"message": "MFA activado"}


class MFADisableRequest(BaseModel):
    code: str


@router.delete("/mfa")
def mfa_disable(req: MFADisableRequest, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Disable MFA after verifying the current TOTP code."""
    user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user or not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="MFA no está activado")
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(req.code.strip(), valid_window=1):
        raise HTTPException(status_code=400, detail="Código MFA incorrecto")
    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    return {"message": "MFA desactivado"}


# ── User management ───────────────────────────────────────────────────────────

@router.get("/users")
def list_users(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    users = db.query(DBUser).all()
    return [
        {"username": u.username, "must_change_password": bool(u.must_change_password),
         "totp_enabled": bool(u.totp_enabled), "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in users
    ]


class CreateUserRequest(BaseModel):
    username: str
    password: str


@router.post("/users")
def create_user(req: CreateUserRequest, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    if len(req.username) < 3:
        raise HTTPException(status_code=400, detail="El username debe tener al menos 3 caracteres")
    if len(req.password) < 12:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 12 caracteres")
    if db.query(DBUser).filter(DBUser.username == req.username).first():
        raise HTTPException(status_code=409, detail="El usuario ya existe")
    user = DBUser(username=req.username, password_hash=hash_password(req.password), must_change_password=True)
    db.add(user)
    db.commit()
    log_event(db, current_user.username, "USER_CREATED", detail=req.username)
    return {"message": "Usuario creado", "username": req.username}


@router.delete("/users/{username}")
def delete_user(username: str, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")
    user = db.query(DBUser).filter(DBUser.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    log_event(db, current_user.username, "USER_DELETED", detail=username)
    db.delete(user)
    db.commit()
    return {"message": "Usuario eliminado"}
