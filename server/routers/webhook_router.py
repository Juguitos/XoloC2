"""Webhook notification settings and dispatcher."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict
import httpx
from auth import require_auth, User

router = APIRouter(prefix="/api/settings/webhook", tags=["webhook"])

_WEBHOOK_FILE = Path(__file__).parent.parent / "webhook.json"

_DEFAULT_EVENTS = {
    "new_agent": True,
    "login": True,
    "login_fail": True,
    "agent_deleted": False,
    "task_sent": False,
}


def load_webhook_config() -> dict:
    if _WEBHOOK_FILE.exists():
        try:
            return json.loads(_WEBHOOK_FILE.read_text())
        except Exception:
            pass
    return {"url": "", "enabled": False, "events": _DEFAULT_EVENTS}


def save_webhook_config(data: dict):
    _WEBHOOK_FILE.write_text(json.dumps(data, indent=2))


class WebhookConfig(BaseModel):
    url: str
    enabled: bool
    events: Dict[str, bool]


@router.get("")
def get_webhook(_: User = Depends(require_auth)):
    cfg = load_webhook_config()
    # Ensure all default event keys exist
    for k, v in _DEFAULT_EVENTS.items():
        cfg.setdefault("events", {}).setdefault(k, v)
    return cfg


@router.post("")
def set_webhook(req: WebhookConfig, _: User = Depends(require_auth)):
    save_webhook_config({"url": req.url, "enabled": req.enabled, "events": req.events})
    return {"message": "Saved"}


@router.post("/test")
async def test_webhook(_: User = Depends(require_auth)):
    cfg = load_webhook_config()
    if not cfg.get("url"):
        raise HTTPException(status_code=400, detail="No webhook URL configured")
    ok = await _dispatch(cfg["url"], "test", {"message": "XoloC2 webhook test ✓"})
    if not ok:
        raise HTTPException(status_code=502, detail="Webhook delivery failed — check the URL")
    return {"message": "Test notification sent"}


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _dispatch(url: str, event: str, data: dict) -> bool:
    """HTTP POST to webhook URL. Returns True on success."""
    try:
        body = _build_payload(event, data)
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(url, json=body)
            return r.status_code < 300
    except Exception:
        return False


_COLORS = {
    "new_agent":     0x22C55E,  # green
    "login":         0x3B82F6,  # blue
    "login_fail":    0xEF4444,  # red
    "agent_deleted": 0xF59E0B,  # amber
    "task_sent":     0x8B5CF6,  # purple
    "test":          0xF59E0B,  # amber
}

_TITLES = {
    "new_agent":     "⚡ New Agent Connected",
    "login":         "🔑 Operator Login",
    "login_fail":    "⚠ Failed Login Attempt",
    "agent_deleted": "🗑 Agent Deleted",
    "task_sent":     "📋 Task Sent",
    "test":          "🔔 Test Notification",
}


def _build_payload(event: str, data: dict) -> dict:
    """Discord-compatible embed + flat keys for generic webhooks."""
    fields = [
        {"name": k.replace("_", " ").title(), "value": str(v)[:1024], "inline": True}
        for k, v in data.items()
    ]
    return {
        # Discord embeds
        "embeds": [{
            "title": _TITLES.get(event, f"XoloC2: {event}"),
            "color": _COLORS.get(event, 0x6B7280),
            "fields": fields[:10],
            "footer": {"text": "XoloC2 C2 Framework"},
        }],
        # Generic webhook fallback (flat keys)
        "event": event,
        **data,
    }


async def notify(event: str, data: dict):
    """Fire-and-forget webhook notification. Call with await from async context."""
    cfg = load_webhook_config()
    if not cfg.get("enabled") or not cfg.get("url"):
        return
    if not cfg.get("events", {}).get(event, True):
        return
    asyncio.create_task(_dispatch(cfg["url"], event, data))
