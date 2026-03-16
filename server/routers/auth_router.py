from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, User
from auth import hash_password, verify_password, create_token, require_auth
import config
import time
import threading

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Simple in-memory rate limiter for login ───────────────────────────────────
# Tracks failed attempts per IP: {ip: [timestamp, ...]}
_failed: dict[str, list[float]] = {}
_failed_lock = threading.Lock()

_MAX_ATTEMPTS = 10       # max failures before lockout
_WINDOW_SECS  = 300      # rolling 5-minute window
_LOCKOUT_SECS = 900      # 15-minute lockout after exceeding limit


def _check_rate_limit(ip: str):
    now = time.time()
    with _failed_lock:
        attempts = [t for t in _failed.get(ip, []) if now - t < _WINDOW_SECS]
        if len(attempts) >= _MAX_ATTEMPTS:
            wait = int(_LOCKOUT_SECS - (now - attempts[-_MAX_ATTEMPTS]))
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Try again in {wait}s.",
            )
        _failed[ip] = attempts


def _record_failure(ip: str):
    now = time.time()
    with _failed_lock:
        attempts = [t for t in _failed.get(ip, []) if now - t < _WINDOW_SECS]
        attempts.append(now)
        _failed[ip] = attempts


def _clear_failures(ip: str):
    with _failed_lock:
        _failed.pop(ip, None)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )

    _check_rate_limit(ip)

    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        _record_failure(ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    _clear_failures(ip)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    token = create_token({"sub": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "must_change_password": user.must_change_password,
        "expires_at": int(expires_at.timestamp()),
    }


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(req.new_password) < 12:
        raise HTTPException(status_code=400, detail="New password must be at least 12 characters")

    user.password_hash = hash_password(req.new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "Password changed successfully"}


@router.get("/me")
def me(user: User = Depends(require_auth)):
    return {
        "username": user.username,
        "must_change_password": user.must_change_password,
    }
