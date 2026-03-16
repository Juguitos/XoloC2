import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
import database
from routers.auth_router import router as auth_router
from routers.agents_router import router as agents_router
from routers.beacon_router import router as beacon_router
from routers.info_router import router as info_router
from routers.settings_router import router as settings_router, load_whitelist
from routers.pty_router import router as pty_router
from routers.tunnel_router import router as tunnel_router
from websocket_manager import manager as ws_manager
from auth import decode_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="XoloC2", docs_url=None, redoc_url=None, lifespan=lifespan)

_BASE = os.path.dirname(__file__)

app.mount("/static", StaticFiles(directory=os.path.join(_BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))

app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(beacon_router)
app.include_router(info_router)
app.include_router(settings_router)
app.include_router(pty_router)
app.include_router(tunnel_router)


@app.middleware("http")
async def ip_whitelist_middleware(request: Request, call_next):
    path = request.url.path
    # Beacon endpoints are accessed by target machines, never restrict them
    if path.startswith("/api/beacon/") or path.startswith("/static/"):
        return await call_next(request)

    wl = load_whitelist()
    if not wl.get("enabled", False):
        return await call_next(request)

    allowed = {e["ip"] for e in wl.get("entries", [])}
    client_ip = (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
    )
    if client_ip not in allowed:
        return JSONResponse({"detail": "Access denied — IP not whitelisted"}, status_code=403)

    return await call_next(request)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(...)):
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=1008)
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive pings
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
async def serve_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request}, headers=NO_CACHE)


@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard/{path:path}", response_class=HTMLResponse)
async def serve_dashboard(request: Request, path: str = ""):
    return templates.TemplateResponse("dashboard.html", {"request": request}, headers=NO_CACHE)
