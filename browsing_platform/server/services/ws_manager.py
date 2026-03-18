"""
Generic thread-safe WebSocket pub/sub manager.

Usage
-----
1. Call ``set_event_loop(loop)`` once at server startup (from the async context).
2. Create one ``BroadcastManager`` instance per logical channel (e.g. one for
   incorporation, one for uploads, …).
3. Call ``instance.broadcast(msg)`` from any thread to push a dict to every
   connected WebSocket subscriber.
4. In the WebSocket route, call ``instance.subscribe()`` to get a per-client
   asyncio.Queue, and ``instance.unsubscribe(q)`` in the finally block.

All ``BroadcastManager`` instances automatically share the single event loop
registered via ``set_event_loop()``.
"""

import asyncio
import threading
from typing import Optional

_loop: Optional[asyncio.AbstractEventLoop] = None
_BUFFER_MAX_DEFAULT = 500


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Register the running event loop. Call once from the server lifespan."""
    global _loop
    _loop = loop


class BroadcastManager:
    """
    Thread-safe pub/sub hub for one logical WebSocket channel.

    - ``subscribe()``   — returns an asyncio.Queue pre-loaded with buffered
                          messages so late-joining clients get context.
    - ``unsubscribe()`` — removes the queue and stops delivery.
    - ``broadcast()``   — pushes a message to all current subscribers; safe to
                          call from any thread (uses call_soon_threadsafe).
    - ``clear_buffer()``— wipe the replay buffer (e.g. at the start of a new job).
    """

    def __init__(self, buffer_max: int = _BUFFER_MAX_DEFAULT):
        self._buffer_max = buffer_max
        self._lock = threading.Lock()
        self._subscribers: set[asyncio.Queue] = set()
        self._buffer: list[dict] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers.add(q)
            for msg in self._buffer:
                q.put_nowait(msg)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def broadcast(self, msg: dict) -> None:
        with self._lock:
            self._buffer.append(msg)
            if len(self._buffer) > self._buffer_max:
                self._buffer = self._buffer[-self._buffer_max:]
            queues = list(self._subscribers)
        if _loop is None:
            return
        for q in queues:
            _loop.call_soon_threadsafe(q.put_nowait, msg)

    def clear_buffer(self) -> None:
        with self._lock:
            self._buffer = []
