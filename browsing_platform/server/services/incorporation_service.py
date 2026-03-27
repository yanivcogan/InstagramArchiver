"""
IncorporationManager — manages the lifecycle of a single incorporation job
(concurrency gate, cancel flag, DB records).

WebSocket broadcasting is handled by the module-level ``incorporation_ws``
BroadcastManager instance. Only messages that are explicitly intended for the
client should be passed to it; backend logging stays in the standard logger.
"""

import asyncio
import logging
import os
import threading
import traceback
from datetime import datetime, timezone
from typing import Optional

from browsing_platform.server.services.ws_manager import BroadcastManager
from db_loaders.archives_db_loader import register_archives, parse_archives, extract_entities
from db_loaders.thumbnail_generator import generate_missing_thumbnails
from utils import db

logger = logging.getLogger(__name__)

# One broadcast channel dedicated to incorporation progress.
# Import this in routes/incorporate.py for the WebSocket endpoint.
incorporation_ws = BroadcastManager()


class IncorporationManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._current_job_id: Optional[int] = None
        self._cancel_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def try_start(self, triggered_by_user_id: Optional[int], triggered_by_ip: Optional[str]) -> int:
        """Start an incorporation run. Returns the new job_id.

        Raises RuntimeError if a job is already running.
        """
        with self._lock:
            if self._running:
                raise RuntimeError("An incorporation job is already running")
            job_id = db.execute_query(
                "INSERT INTO incorporation_job (status, triggered_by_user_id, triggered_by_ip, started_at) "
                "VALUES ('running', %(user_id)s, %(ip)s, NOW())",
                {"user_id": triggered_by_user_id, "ip": triggered_by_ip},
                return_type="id",
            )
            self._current_job_id = job_id
            self._running = True
            self._cancel_event.clear()
            incorporation_ws.clear_buffer()
        return job_id

    def finish(self, job_id: int, status: str, error_message: Optional[str] = None):
        db.execute_query(
            """UPDATE incorporation_job
               SET status = %(s)s, completed_at = %(t)s, error = %(e)s
               WHERE id = %(id)s""",
            {
                "s": status,
                "t": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "e": error_message,
                "id": job_id,
            },
            return_type="none",
        )
        with self._lock:
            self._running = False
            self._current_job_id = None

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def current_job_id(self) -> Optional[int]:
        with self._lock:
            return self._current_job_id

    def request_cancel(self):
        """Signal the running job to stop after the current archive completes."""
        self._cancel_event.set()

    def is_cancel_requested(self) -> bool:
        return self._cancel_event.is_set()


# Module-level singleton
manager = IncorporationManager()


def _run_incorporation(job_id: int):
    """Entry point for the background thread.

    Only messages explicitly passed to incorporation_ws.broadcast() will reach
    the client. All other log output stays server-side.
    """
    def emit(text: str, msg_type: str = "status"):
        logger.info(text)
        incorporation_ws.broadcast({"type": msg_type, "text": text})

    cancel = manager.is_cancel_requested
    error_message = None
    status = "completed"
    try:
        emit("Starting incorporation pipeline…")

        emit("Part A — registering archives")
        register_archives(limit=100 if os.getenv("BROWSING_PLATFORM_DEV") == "1" else None, cancel_check=cancel, emit=emit)

        emit("Part B — parsing HAR files")
        parse_archives(cancel_check=cancel, emit=emit)

        emit("Part C — extracting entities")
        extract_entities(cancel_check=cancel, emit=emit)

        emit("Part D — generating thumbnails")
        # Use a manually managed loop instead of asyncio.run() to avoid blocking
        # on shutdown_default_executor(). asyncio.run() waits for ALL executor
        # threads to finish before returning — including any cv2 threads that
        # survived an asyncio.wait_for timeout and are still running. Those
        # zombie threads would hang the pipeline indefinitely.
        _loop = asyncio.new_event_loop()
        try:
            _loop.run_until_complete(generate_missing_thumbnails(cancel_check=cancel, emit=emit))
        finally:
            _loop.close()

        emit("Incorporation complete.")
        incorporation_ws.broadcast({"type": "done", "status": "completed"})

    except InterruptedError:
        error_message = "Cancelled by user"
        status = "failed"
        logger.info(f"Incorporation job {job_id} cancelled by user")
        emit("Job cancelled by user.")
        incorporation_ws.broadcast({"type": "done", "status": "failed", "error": error_message})
    except Exception as e:
        error_message = str(e)
        status = "failed"
        logger.error(f"Incorporation job {job_id} failed: {e}")
        traceback.print_exc()
        emit(f"ERROR: {e}")
        incorporation_ws.broadcast({"type": "done", "status": "failed", "error": error_message})
    finally:
        manager.finish(job_id, status, error_message)


def cleanup_stale_jobs():
    """Mark any jobs left in 'running' state as 'failed' (called at server startup)."""
    db.execute_query(
        "UPDATE incorporation_job SET status = 'failed', error = 'Server restarted while job was running' "
        "WHERE status = 'running'",
        {},
        return_type="none",
    )
    logger.info("Stale incorporation jobs marked as failed")
