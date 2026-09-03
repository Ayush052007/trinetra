"""Engine and session management."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.base import Base

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

def _connect_args() -> dict:
    if _is_sqlite:
        return {"check_same_thread": False}
    # TCP keepalives stop a managed Postgres pooler (Neon, Supabase, RDS) from
    # dropping a connection that is busy on the server but quiet on the wire -
    # which is exactly what a long seeding transaction looks like.
    return {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "connect_timeout": 30,
    }


engine: Engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args(),
    pool_pre_ping=not _is_sqlite,
    # Round-trips dominate over a remote link. Larger pages mean far fewer of
    # them when inserting the seed corpus.
    insertmanyvalues_page_size=1000,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        # FK enforcement is off by default in SQLite; the schema relies on it.
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """Create any missing tables. Alembic owns versioned changes."""
    from app.db import models, models_safety  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
