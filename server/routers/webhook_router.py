"""Webhook notification settings and dispatcher."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import asyncio
from datetime import datetime, timezone
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
    "test":          0x6B7280,  # gray
}

_TITLES = {
    "new_agent":     "New Agent Connected",
    "login":         "Operator Login",
    "login_fail":    "Failed Login Attempt",
    "agent_deleted": "Agent Deleted",
    "task_sent":     "Task Dispatched",
    "test":          "Test Notification",
}

_ICONS = {
    "new_agent":     "https://cdn.jsdelivr.net/npm/twemoji@14/assets/72x72/26a1.png",
    "login":         "https://cdn.jsdelivr.net/npm/twemoji@14/assets/72x72/1f511.png",
    "login_fail":    "https://cdn.jsdelivr.net/npm/twemoji@14/assets/72x72/26a0.png",
    "agent_deleted": "https://cdn.jsdelivr.net/npm/twemoji@14/assets/72x72/1f5d1.png",
    "task_sent":     "https://cdn.jsdelivr.net/npm/twemoji@14/assets/72x72/1f4cb.png",
    "test":          "https://cdn.jsdelivr.net/npm/twemoji@14/assets/72x72/1f514.png",
}

# Per-event field definitions: list of (label, data_key, inline)
_FIELDS: dict[str, list[tuple[str, str, bool]]] = {
    "new_agent": [
        ("Hostname",  "hostname", True),
        ("User",      "user",     True),
        ("Internal IP", "ip",    True),
        ("OS",        "os",       False),
    ],
    "login": [
        ("Operator",  "user",     True),
        ("From IP",   "ip",       True),
    ],
    "login_fail": [
        ("Username",  "user",     True),
        ("From IP",   "ip",       True),
    ],
    "agent_deleted": [
        ("Hostname",  "hostname", True),
        ("IP",        "ip",       True),
        ("Deleted by", "operator", True),
    ],
    "task_sent": [
        ("Agent",     "agent",    True),
        ("Operator",  "operator", True),
        ("Command",   "command",  False),
    ],
}


def _build_payload(event: str, data: dict) -> dict:
    """Discord-compatible embed + flat keys for generic webhooks."""
    field_defs = _FIELDS.get(event)
    if field_defs:
        fields = [
            {"name": label, "value": f"`{str(data[key])[:1000]}`", "inline": inline}
            for label, key, inline in field_defs
            if key in data
        ]
    else:
        fields = [
            {"name": k.replace("_", " ").title(), "value": f"`{str(v)[:1000]}`", "inline": True}
            for k, v in data.items()
        ]

    ts = datetime.now(timezone.utc).isoformat()

    return {
        "username": "XoloC2",
        # Discord embeds
        "embeds": [{
            "author": {
                "name": _TITLES.get(event, f"XoloC2 \u2022 {event}"),
                "icon_url": _ICONS.get(event),
            },
            "color": _COLORS.get(event, 0x6B7280),
            "fields": fields[:10],
            "footer": {"text": "XoloC2"},
            "timestamp": ts,
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
