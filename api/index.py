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

from app.main import app  # noqa: E402

__all__ = ["app"]
