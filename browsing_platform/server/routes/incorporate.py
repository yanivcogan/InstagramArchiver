import asyncio
import json
import logging
import os
import threading
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from browsing_platform.server.services.incorporation_service import manager, _run_incorporation, incorporation_ws
from browsing_platform.server.services.permissions import auth_admin_access
from browsing_platform.server.services.token_manager import check_token
from utils import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incorporate", tags=["incorporate"])


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

@router.post("/start")
def start(
    request: Request,
    background_tasks: BackgroundTasks,
    permissions=Depends(auth_admin_access),
):
    user_id = getattr(permissions, "user_id", None)
    client_ip = (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else None)
    )
    try:
        job_id = manager.try_start(triggered_by_user_id=user_id, triggered_by_ip=client_ip)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    background_tasks.add_task(_run_in_thread, job_id)
    return {"status": "started", "job_id": job_id}


def _run_in_thread(job_id: int):
    """Wrapper that launches the incorporation work in a daemon thread."""
    t = threading.Thread(target=_run_incorporation, args=(job_id,), daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

@router.post("/stop")
def stop(_=Depends(auth_admin_access)):
    if not manager.is_running():
        raise HTTPException(status_code=409, detail="No incorporation job is currently running")
    manager.request_cancel()
    return {"status": "cancel_requested"}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status")
def status(_=Depends(auth_admin_access)):
    job_id = manager.current_job_id()
    if manager.is_running() and job_id is not None:
        row = db.execute_query(
            "SELECT * FROM incorporation_job WHERE id = %(id)s",
            {"id": job_id},
            return_type="single_row",
        )
        return {"running": True, "job": row}
    return {"running": False, "job": None}


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.get("/history")
def history(_=Depends(auth_admin_access)):
    rows = db.execute_query(
        "SELECT * FROM incorporation_job ORDER BY started_at DESC LIMIT 50",
        {},
        return_type="rows",
    )
    return {"jobs": rows or []}


# ---------------------------------------------------------------------------
# WebSocket — real-time log stream
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: Optional[str] = Query(default=None)):
    # Auth: dev bypass or validate admin token
    is_dev = os.getenv("BROWSING_PLATFORM_DEV") == "1"
    if not is_dev:
        perms = check_token(token)
        if not perms.valid or not perms.admin:
            await websocket.close(code=4003)
            return

    await websocket.accept()
    q = incorporation_ws.subscribe()
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30)
                await websocket.send_text(json.dumps(msg))
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        incorporation_ws.unsubscribe(q)
