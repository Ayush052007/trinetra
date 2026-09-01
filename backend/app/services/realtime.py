"""In-process pub/sub for WebSocket broadcasting.

Single-process only. A multi-worker deployment needs a shared broker
(Redis pub/sub or similar) - documented in docs/ARCHITECTURE.md rather than
pretended away. The client also polls as a fallback, so a dropped socket
degrades the experience rather than breaking it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("trinetra.realtime")

_subscribers: set[asyncio.Queue] = set()
_recent: deque[dict[str, Any]] = deque(maxlen=100)
_sequence = 0


def subscribe() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    _subscribers.discard(queue)


def broadcast(message: dict[str, Any]) -> None:
    """Publish an event. Safe to call from sync request handlers."""
    global _sequence
    _sequence += 1
    envelope = {
        "seq": _sequence,
        "at": datetime.now(UTC).isoformat(),
        **message,
    }
    _recent.append(envelope)
    dead = []
    for queue in _subscribers:
        try:
            queue.put_nowait(envelope)
        except asyncio.QueueFull:
            # A client that cannot keep up is dropped rather than blocking
            # the request that produced the event.
            dead.append(queue)
        except Exception as exc:  # pragma: no cover
            logger.warning("Broadcast failed: %s", exc)
            dead.append(queue)
    for queue in dead:
        _subscribers.discard(queue)


def recent(since_seq: int = 0) -> list[dict[str, Any]]:
    """Events after `since_seq`, for polling clients and reconnects."""
    return [e for e in _recent if e["seq"] > since_seq]


def current_sequence() -> int:
    return _sequence


def subscriber_count() -> int:
    return len(_subscribers)
