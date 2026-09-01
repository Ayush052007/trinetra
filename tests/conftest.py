"""Shared pytest fixtures.

Tests run against the seeded development database through FastAPI's in-process
TestClient, so they exercise the real routing, dependency and RBAC stack
without needing a running server.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in ("backend", "database", "ai", "graph"):
    sys.path.insert(0, str(ROOT / path))


@pytest.fixture(scope="session")
def credentials() -> dict[str, str]:
    """Seeded account passwords, read from the gitignored handover file."""
    path = ROOT / "CREDENTIALS.md"
    if not path.exists():
        pytest.skip("CREDENTIALS.md missing - run the seed first")
    creds: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`([A-Z]+-\d+)`\s*\|[^|]*\|[^|]*\|[^|]*\|\s*`([^`]+)`", line)
        if m:
            creds[m.group(1)] = m.group(2)
    if not creds:
        pytest.skip("No credentials parsed from CREDENTIALS.md")
    return creds


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def db():
    from app.db.session import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


def _sign_in(client, credentials, service_id: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"service_id": service_id, "password": credentials[service_id]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def investigator(client, credentials) -> dict[str, str]:
    return _sign_in(client, credentials, "IO-114")


@pytest.fixture(scope="session")
def supervisor(client, credentials) -> dict[str, str]:
    return _sign_in(client, credentials, "SI-207")


@pytest.fixture(scope="session")
def analyst(client, credentials) -> dict[str, str]:
    return _sign_in(client, credentials, "AN-331")


@pytest.fixture(scope="session")
def safety_officer(client, credentials) -> dict[str, str]:
    return _sign_in(client, credentials, "WSO-052")


@pytest.fixture(scope="session")
def admin(client, credentials) -> dict[str, str]:
    return _sign_in(client, credentials, "ADM-001")
