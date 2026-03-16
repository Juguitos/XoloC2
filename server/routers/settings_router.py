from pathlib import Path
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import List
import json
from auth import require_auth, User

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
    # Priority: explicit proxy headers → direct connection IP
    xff = request.headers.get("X-Forwarded-For", "")
    ip = (
        request.headers.get("X-Real-IP")
        or (xff.split(",")[0].strip() if xff else None)
        or (request.client.host if request.client else "unknown")
    )
    return {"ip": ip or "unknown"}
