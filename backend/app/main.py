"""TRINETRA application entrypoint."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings

logger = logging.getLogger("trinetra")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


# Set while first-boot seeding is running, so /health can say so and the client
# can show "initialising" rather than a bare failed sign-in.
_startup_state: dict[str, object] = {"seeding": False, "seed_error": None}


def _database_is_empty() -> bool:
    """True when no users exist, i.e. the database has never been seeded."""
    from sqlalchemy import func, select

    from app.db.models import User
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return (db.scalar(select(func.count()).select_from(User)) or 0) == 0
    except Exception:
        return False
    finally:
        db.close()


def _run_first_boot_seed() -> None:
    """Populate an empty database on first boot.

    Only reachable when AUTO_SEED is on and the users table is empty, so it
    cannot overwrite an existing deployment's data.
    """
    _startup_state["seeding"] = True
    try:
        from app.db.seed_bulk import seed_all

        logger.info("Empty database detected - running first-boot seed...")
        started = time.perf_counter()
        summary = seed_all(
            reset=False, with_corpus=settings.SEED_WITH_CORPUS, quiet=True
        )
        logger.info(
            "First-boot seed complete in %.1fs: %s users, %s entities",
            time.perf_counter() - started,
            summary.get("users"), summary.get("entities"),
        )
    except Exception as exc:
        _startup_state["seed_error"] = str(exc)
        logger.exception("First-boot seed failed: %s", exc)
    finally:
        _startup_state["seeding"] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    for warning in settings.validate_runtime():
        logger.warning(warning)

    from app.db.session import create_all

    create_all()

    from app.db.session import SessionLocal
    from app.services import graph_service

    # Build the graph projection and warm the analytics cache in the background
    # so the first request to hit an analytics page does not pay for it.
    def warm_up() -> None:
        if settings.AUTO_SEED and _database_is_empty():
            _run_first_boot_seed()

        db = SessionLocal()
        try:
            repo = graph_service.get_graph(db)
            snapshot = repo.snapshot()
            logger.info(
                "Knowledge graph ready: %s backend, %d nodes, %d edges",
                repo.backend_name(), snapshot.node_count, snapshot.edge_count,
            )
            started = time.perf_counter()
            analytics = graph_service.graph_analytics(db)
            logger.info(
                "Graph analytics warmed in %.1fs (betweenness %s)",
                time.perf_counter() - started,
                "exact" if analytics["betweenness_exact"] else
                f"estimated from {analytics['betweenness_pivots']} pivots",
            )
        except Exception as exc:  # pragma: no cover - startup diagnostics only
            logger.error("Startup warm-up failed: %s", exc)
        finally:
            db.close()

    threading.Thread(target=warm_up, name="trinetra-warmup", daemon=True).start()

    logger.info(
        "%s v%s ready (%s, data=%s)",
        settings.APP_NAME, settings.VERSION, settings.ENVIRONMENT,
        settings.DATA_CLASSIFICATION,
    )
    yield


app = FastAPI(
    title=f"{settings.APP_NAME} - {settings.APP_SUBTITLE}",
    version=settings.VERSION,
    description=(
        "Investigative decision-support platform. All analytical output is "
        "advisory and requires authorised human validation. The platform does "
        "not determine guilt."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Attach a request id and conservative security headers."""
    request_id = uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
    # In development the client is served unbundled, so a cached module can
    # silently mask an edit. Revalidate every time; production can cache.
    if not settings.is_production and request.url.path.startswith(("/src/", "/vendor/")):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


# ---------------------------------------------------------- error handling


def _error(status_code: int, message, request: Request, code: str | None = None):
    """Uniform error envelope. Never leaks internals to the caller."""
    body: dict = {
        "error": {
            "code": code or f"http_{status_code}",
            "request_id": getattr(request.state, "request_id", None),
        }
    }
    if isinstance(message, dict):
        body["error"].update(message)
        body["error"].setdefault("message", "Request could not be completed.")
    else:
        body["error"]["message"] = str(message)
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    response = _error(exc.status_code, exc.detail, request)
    if exc.headers:
        for key, value in exc.headers.items():
            response.headers[key] = value
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    fields = [
        {
            "field": ".".join(str(p) for p in err.get("loc", []) if p != "body"),
            "message": err.get("msg", "Invalid value"),
        }
        for err in exc.errors()
    ]
    return _error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        {"message": "Some fields need attention.", "fields": fields},
        request,
        code="validation_error",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log the stack trace server-side; return an opaque message to the client."""
    logger.exception(
        "Unhandled error [%s] on %s %s",
        getattr(request.state, "request_id", "-"), request.method, request.url.path,
    )
    return _error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        {
            "message": (
                "An unexpected error occurred. The incident has been logged. "
                "Quote the request ID when reporting this."
            )
        },
        request,
        code="internal_error",
    )


# ---------------------------------------------------------------- routing

from app.api.v1 import (  # noqa: E402
    analytics,
    audit,
    auth,
    cases,
    dashboard,
    entities,
    graph,
    ingestion,
    nlp,
    reports,
    resolution,
    safety,
    ws,
)

API_PREFIX = "/api/v1"
for module in (
    auth, dashboard, entities, graph, cases, analytics, nlp, resolution,
    ingestion, reports, audit, safety,
):
    app.include_router(module.router, prefix=API_PREFIX)
app.include_router(ws.router)


@app.get(f"{API_PREFIX}/health", tags=["system"])
def health() -> dict:
    from app.db.session import SessionLocal
    from sqlalchemy import text

    database_ok = True
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        database_ok = False

    seeding = bool(_startup_state.get("seeding"))
    return {
        "status": "initialising" if seeding else ("ok" if database_ok else "degraded"),
        "initialising": seeding,
        "message": (
            "First-time setup is running. Sign-in becomes available once it "
            "completes - this takes about a minute."
        ) if seeding else None,
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if database_ok else "unavailable",
        "graph_backend": settings.GRAPH_BACKEND,
        "data_classification": settings.DATA_CLASSIFICATION,
    }


@app.get(f"{API_PREFIX}/config", tags=["system"])
def public_config() -> dict:
    """Client bootstrap data. Contains no secrets."""
    from app.db.models_safety import IncidentType

    return {
        "app": {
            "name": settings.APP_NAME,
            "subtitle": settings.APP_SUBTITLE,
            "tagline": settings.APP_TAGLINE,
            "version": settings.VERSION,
        },
        "deployment": {
            "unit": settings.DEPLOYMENT_UNIT,
            "organisation": settings.DEPLOYMENT_ORG,
            "division": settings.DEPLOYMENT_DIVISION,
        },
        "classification": {
            "label": settings.DATA_CLASSIFICATION,
            "show_banner": settings.SHOW_CLASSIFICATION_BANNER,
            "message": (
                "SYNTHETIC DATA - This deployment contains generated and fictional "
                "records for demonstration and testing. It holds no operational "
                "police data and must not be used for operational decisions."
            ),
        },
        "map": {
            "tile_url": settings.MAP_TILE_URL,
            "attribution": settings.MAP_ATTRIBUTION,
            "offline_mode": not settings.MAP_TILE_URL,
        },
        "integrations": {
            "device_gps": settings.ENABLE_DEVICE_GPS,
            "emergency_dispatch": settings.ENABLE_EMERGENCY_DISPATCH,
            "sms_gateway": settings.ENABLE_SMS_GATEWAY,
            "telecom_cdr_feed": settings.ENABLE_TELECOM_CDR_FEED,
            "rto_lookup": settings.ENABLE_RTO_LOOKUP,
            "cctns_sync": settings.ENABLE_CCTNS_SYNC,
            "notice": (
                "Disabled integrations are structured but not connected. They "
                "require authorisation and configuration before use."
            ),
        },
        "incident_types": [
            {"key": t, "label": IncidentType.LABELS[t]} for t in IncidentType.ALL
        ],
        "session": {
            "access_token_minutes": settings.ACCESS_TOKEN_MINUTES,
            "max_failed_logins": settings.MAX_FAILED_LOGINS,
            "lockout_minutes": settings.LOCKOUT_MINUTES,
        },
        "disclaimer": (
            "TRINETRA is an investigative decision-support system. It does not "
            "determine guilt and does not replace authorised human judgement."
        ),
    }


# ------------------------------------------------------------ static client

if FRONTEND_DIR.exists():
    app.mount(
        "/vendor", StaticFiles(directory=FRONTEND_DIR / "vendor"), name="vendor"
    )
    app.mount("/src", StaticFiles(directory=FRONTEND_DIR / "src"), name="src")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """Client-side routing: serve the shell for any non-API path."""
        if full_path.startswith(("api/", "vendor/", "src/", "ws/")):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
        return FileResponse(FRONTEND_DIR / "index.html")
