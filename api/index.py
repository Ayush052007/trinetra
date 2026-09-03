"""Vercel serverless entry point.

Vercel's Python runtime looks for an ASGI application named `app` in a module
under api/. Everything below adjusts for the serverless execution model:

  * the process is recreated per cold start, so no background warm-up thread
  * the filesystem is read-only outside /tmp, so the database must be external
  * WebSockets are not supported, so the client's polling fallback takes over

See docs/VERCEL.md for what this costs relative to a normal server.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for package in ("backend", "database", "ai", "graph"):
    path = str(PROJECT_ROOT / package)
    if path not in sys.path:
        sys.path.insert(0, path)

# Tell the application it is running serverless before anything imports config.
os.environ.setdefault("SERVERLESS", "true")

from app.main import app as _app  # noqa: E402


async def app(scope, receive, send):
    """Diagnostic wrapper: report exactly what Vercel hands the function."""
    if scope["type"] == "http" and scope.get("path", "").rstrip("/") == "/__vercel_probe":
        import json

        headers = {
            k.decode(): v.decode() for k, v in scope.get("headers", [])
        }
        payload = json.dumps({
            "path": scope.get("path"),
            "raw_path": scope.get("raw_path", b"").decode(errors="replace")
            if isinstance(scope.get("raw_path"), bytes) else scope.get("raw_path"),
            "query_string": scope.get("query_string", b"").decode(),
            "root_path": scope.get("root_path"),
            "headers": headers,
        }, indent=2).encode()
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": payload})
        return
    await _app(scope, receive, send)


__all__ = ["app"]
