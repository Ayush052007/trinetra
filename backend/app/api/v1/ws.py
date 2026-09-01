"""WebSocket and polling endpoints for live updates."""

from __future__ import annotations

import asyncio
import logging

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.core.deps import get_current_user
from app.core.security import decode_token
from app.db.models import User
from app.db.session import SessionLocal
from app.services import realtime

logger = logging.getLogger("trinetra.ws")
router = APIRouter(tags=["realtime"])


@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket, token: str = Query(...)) -> None:
    """Live event stream.

    The token arrives as a query parameter because browsers cannot set
    Authorization headers on WebSocket handshakes. It is verified exactly as a
    bearer token would be, and the socket closes on any failure.
    """
    try:
        payload = decode_token(token)
        if payload.get("typ") != "access":
            raise jwt.InvalidTokenError("wrong token type")
    except jwt.PyJWTError:
        await websocket.close(code=4401, reason="Invalid or expired token")
        return

    db = SessionLocal()
    try:
        user = db.get(User, int(payload.get("sub", 0)))
        if user is None or not user.is_active:
            await websocket.close(code=4401, reason="Account not active")
            return
        service_id = user.service_id
    finally:
        db.close()

    await websocket.accept()
    queue = realtime.subscribe()
    try:
        await websocket.send_json({
            "channel": "system",
            "event": "connected",
            "data": {"service_id": service_id, "seq": realtime.current_sequence()},
        })
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=25.0)
                await websocket.send_json(message)
            except asyncio.TimeoutError:
                # Keepalive: proxies drop idle sockets.
                await websocket.send_json({"channel": "system", "event": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover
        logger.info("WebSocket closed: %s", exc)
    finally:
        realtime.unsubscribe(queue)


@router.get("/api/v1/events/poll")
def poll(
    since: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
) -> dict:
    """Polling fallback for clients without a working WebSocket."""
    events = realtime.recent(since)
    return {
        "events": events,
        "seq": realtime.current_sequence(),
        "subscribers": realtime.subscriber_count(),
    }
