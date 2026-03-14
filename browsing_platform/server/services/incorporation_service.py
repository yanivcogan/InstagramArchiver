"""
IncorporationManager — singleton that orchestrates running archives_db_loader
stages in a background thread and streams log output to WebSocket subscribers.

Thread model
------------
FastAPI runs on the main asyncio event loop (main thread).
The incorporation pipeline runs in a daemon thread (via BackgroundTasks).

Messages are pushed from the background thread to each subscriber's asyncio.Queue
using loop.call_soon_threadsafe(), which is the only safe way to touch the queue
from outside the event loop.
"""

import asyncio
import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Optional

from utils import db

logger = logging.getLogger(__name__)

# How many log lines to buffer for late-joining WebSocket clients
_LOG_BUFFER_MAX = 500


class _BroadcastHandler(logging.Handler):
    """Logging handler that forwards records to the IncorporationManager."""

    def __init__(self, manager: "IncorporationManager"):
        super().__init__()
        self._manager = manager

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._manager._broadcast({"type": "log", "text": msg, "level": record.levelname})
        except Exception:
            pass


class IncorporationManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._current_job_id: Optional[int] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscribers: set[asyncio.Queue] = set()
        self._subscribers_lock = threading.Lock()
        self._log_buffer: list[dict] = []
        self._handler: Optional[_BroadcastHandler] = None
        self._cancel_event = threading.Event()

    # ------------------------------------------------------------------
    # Called once at server startup to capture the running event loop
    # ------------------------------------------------------------------

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def try_start(self, triggered_by: Optional[int]) -> int:
        """Start an incorporation run. Returns the new job_id.

        Raises RuntimeError if a job is already running.
        """
        with self._lock:
            if self._running:
                raise RuntimeError("An incorporation job is already running")
            job_id = db.execute_query(
                "INSERT INTO incorporation_job (status, triggered_by) VALUES ('running', %(u)s)",
                {"u": triggered_by},
                return_type="id",
            )
            self._current_job_id = job_id
            self._running = True
            self._log_buffer = []
            self._cancel_event.clear()
        return job_id

    def request_cancel(self):
        """Signal the running job to stop after the current stage completes."""
        self._cancel_event.set()

    def is_cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    def finish(self, job_id: int, status: str, error_message: Optional[str] = None):
        db.execute_query(
            """UPDATE incorporation_job
               SET status = %(s)s, completed_at = %(t)s, error_message = %(e)s
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

    # ------------------------------------------------------------------
    # Pub/sub for WebSocket clients
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self._subscribers_lock:
            self._subscribers.add(q)
            # Replay buffered log lines so late joiners see context
            for msg in self._log_buffer:
                q.put_nowait(msg)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        with self._subscribers_lock:
            self._subscribers.discard(q)

    # ------------------------------------------------------------------
    # Internal helpers (called from background thread)
    # ------------------------------------------------------------------

    def _broadcast(self, msg: dict):
        """Thread-safe: push a message to every subscriber queue."""
        with self._subscribers_lock:
            # Keep buffer bounded
            self._log_buffer.append(msg)
            if len(self._log_buffer) > _LOG_BUFFER_MAX:
                self._log_buffer = self._log_buffer[-_LOG_BUFFER_MAX:]
            queues = list(self._subscribers)

        if self._loop is None:
            return
        for q in queues:
            self._loop.call_soon_threadsafe(q.put_nowait, msg)

    def _attach_logging(self):
        fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")
        self._handler = _BroadcastHandler(self)
        self._handler.setFormatter(fmt)
        self._handler.setLevel(logging.DEBUG)
        for name in ("db_loaders", "extractors"):
            logging.getLogger(name).addHandler(self._handler)

    def _detach_logging(self):
        if self._handler:
            for name in ("db_loaders", "extractors"):
                logging.getLogger(name).removeHandler(self._handler)
            self._handler = None


# Module-level singleton
manager = IncorporationManager()


def _run_incorporation(job_id: int):
    """Entry point for the background thread."""
    manager._attach_logging()
    error_message = None
    status = "completed"
    try:
        manager._broadcast({"type": "status", "text": "Starting incorporation pipeline…"})

        import asyncio as _asyncio
        from db_loaders.archives_db_loader import (
            register_archives,
            parse_archives,
            extract_entities,
        )
        from db_loaders.thumbnail_generator import generate_missing_thumbnails

        def check_cancel():
            if manager.is_cancel_requested():
                raise InterruptedError("Cancelled by user")

        manager._broadcast({"type": "status", "text": "Part A — registering archives"})
        register_archives()
        check_cancel()

        manager._broadcast({"type": "status", "text": "Part B — parsing HAR files"})
        parse_archives()
        check_cancel()

        manager._broadcast({"type": "status", "text": "Part C — extracting entities"})
        extract_entities()
        check_cancel()

        manager._broadcast({"type": "status", "text": "Part D — generating thumbnails"})
        _asyncio.run(generate_missing_thumbnails())

        manager._broadcast({"type": "status", "text": "Incorporation complete."})
        manager._broadcast({"type": "done", "status": "completed"})

    except Exception as e:
        error_message = str(e)
        status = "failed"
        logger.error(f"Incorporation job {job_id} failed: {e}")
        traceback.print_exc()
        manager._broadcast({"type": "status", "text": f"ERROR: {e}"})
        manager._broadcast({"type": "done", "status": "failed", "error": error_message})
    finally:
        manager._detach_logging()
        manager.finish(job_id, status, error_message)


def cleanup_stale_jobs():
    """Mark any jobs left in 'running' state as 'failed' (called at server startup)."""
    db.execute_query(
        "UPDATE incorporation_job SET status = 'failed', error_message = 'Server restarted while job was running' "
        "WHERE status = 'running'",
        {},
        return_type="none",
    )
    logger.info("Stale incorporation jobs marked as failed")
