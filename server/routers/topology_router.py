"""
Topology endpoint — computes network graph from agents + neighbor scan results.
No extra DB model needed: parses the output of the latest 'neighbors' task per agent.
"""
import re
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, Agent, Task
from auth import require_auth, User
from datetime import datetime, timezone

router = APIRouter(prefix="/api/topology", tags=["topology"])

_IP_RE = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')
_SKIP  = {"0.0.0.0", "255.255.255.255", "127.0.0.1"}


@router.get("")
def get_topology(db: Session = Depends(get_db), _: User = Depends(require_auth)):
    agents = db.query(Agent).all()
    nodes: dict = {}   # ip → node dict
    edges: list = []   # {from, to}

    for a in agents:
        if not a.ip_internal:
            continue

        last_seen_dt = a.last_seen
        if last_seen_dt and last_seen_dt.tzinfo is None:
            last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
        online = False
        if last_seen_dt:
            secs = (datetime.now(timezone.utc) - last_seen_dt).total_seconds()
            online = secs < (a.sleep_interval * 3 + 15)

        nodes[a.ip_internal] = {
            "id":       a.ip_internal,
            "type":     "agent",
            "label":    a.hostname or a.ip_internal,
            "ip":       a.ip_internal,
            "agent_id": a.id,
            "online":   online,
            "os":       a.os_info  or "",
            "user":     a.username or "",
        }

        # Parse the most recent completed 'neighbors' task for this agent
        task = (
            db.query(Task)
            .filter(Task.agent_id == a.id,
                    Task.command  == "neighbors",
                    Task.status   == "done")
            .order_by(Task.completed_at.desc())
            .first()
        )
        if not task or not task.output:
            continue

        for ip in _IP_RE.findall(task.output):
            parts = ip.split(".")
            if ip in _SKIP or parts[0] in ("127", "255", "224", "0"):
                continue
            if ip not in nodes:
                nodes[ip] = {
                    "id":       ip,
                    "type":     "host",
                    "label":    ip,
                    "ip":       ip,
                    "agent_id": None,
                    "online":   False,
                    "os":       "",
                    "user":     "",
                }
            edge = {"from": a.ip_internal, "to": ip}
            if edge not in edges:
                edges.append(edge)

    return {"nodes": list(nodes.values()), "edges": edges}
