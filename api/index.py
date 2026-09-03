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
from urllib.parse import parse_qsl, urlencode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for package in ("backend", "database", "ai", "graph"):
    path = str(PROJECT_ROOT / package)
    if path not in sys.path:
        sys.path.insert(0, path)

# Tell the application it is running serverless before anything imports config.
os.environ.setdefault("SERVERLESS", "true")

from app.main import app as fastapi_app  # noqa: E402

# vercel.json rewrites every request to this one function, which means the
# function is handed the literal path "/api/index" and the URL the visitor
# actually asked for is lost - every route then 404s. The rewrite therefore
# carries the original path along in a query parameter, and this wrapper puts
# it back before FastAPI sees the request.
PATH_PARAM = "__vpath"


async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        query = scope.get("query_string", b"").decode("latin-1")
        params = parse_qsl(query, keep_blank_values=True)
        original = None
        remaining = []
        for key, value in params:
            if key == PATH_PARAM and original is None:
                original = value
            else:
                remaining.append((key, value))
        if original is not None:
            scope = dict(scope)
            scope["path"] = "/" + original.lstrip("/")
            scope["raw_path"] = scope["path"].encode("utf-8")
            scope["query_string"] = urlencode(remaining).encode("latin-1")
    await fastapi_app(scope, receive, send)


__all__ = ["app"]
