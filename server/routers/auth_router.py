from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, User
from auth import hash_password, verify_password, create_token, require_auth
import config

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

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
