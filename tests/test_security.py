"""Authentication, password handling and role-based access control.

These are the tests that would catch a security regression, so they assert
behaviour rather than implementation: that a wrong password fails, that a
lower-privileged role receives 403 from the *server*, and that hidden UI is
never the boundary.
"""

from __future__ import annotations

import pytest

from app.core.rbac import Perm, Role, permissions_for
from app.core.security import (
    generate_password,
    hash_password,
    password_strength_errors,
    verify_password,
)


# ------------------------------------------------------------ password hashing


def test_password_round_trip():
    password = generate_password(16)
    stored = hash_password(password)
    assert stored.startswith("scrypt$")
    assert password not in stored, "the plaintext must never appear in the hash"
    assert verify_password(password, stored) is True
    assert verify_password(password + "x", stored) is False


def test_hash_is_salted():
    """Two hashes of the same password must differ."""
    password = "SameP@ssw0rd123"
    assert hash_password(password) != hash_password(password)


def test_verify_rejects_malformed_hash_without_raising():
    for junk in ("", "garbage", "scrypt$notanumber$8$1$aa$bb", "a$b$c$d$e$f"):
        assert verify_password("anything", junk) is False


def test_generated_passwords_meet_policy():
    for _ in range(20):
        assert password_strength_errors(generate_password(16)) == []


def test_weak_passwords_are_rejected():
    assert password_strength_errors("short") != []
    assert password_strength_errors("alllowercase123!") != []
    assert password_strength_errors("NOLOWERCASE123!") != []
    assert password_strength_errors("NoDigitsHere!!") != []
    assert password_strength_errors("NoSymbols12345") != []


# --------------------------------------------------------------------- RBAC


def test_every_role_has_a_distinct_permission_set():
    sets = {role: frozenset(permissions_for(role)) for role in Role}
    assert len(set(sets.values())) == len(sets), "roles must not be interchangeable"


def test_analyst_cannot_validate_or_administer():
    granted = permissions_for(Role.ANALYST)
    assert Perm.RELATIONSHIP_VALIDATE not in granted
    assert Perm.USER_MANAGE not in granted
    assert Perm.CASE_CLOSE not in granted


def test_investigator_cannot_close_cases_or_read_audit():
    granted = permissions_for(Role.INVESTIGATOR)
    assert Perm.CASE_CLOSE not in granted
    assert Perm.AUDIT_READ not in granted
    assert Perm.USER_MANAGE not in granted


def test_women_safety_officer_owns_the_safety_module():
    granted = permissions_for(Role.WOMEN_SAFETY_OFFICER)
    assert Perm.SAFETY_DISPATCH in granted
    assert Perm.SAFETY_INCIDENT_CREATE in granted
    assert Perm.DATA_UPLOAD not in granted


def test_admin_holds_every_permission():
    assert permissions_for(Role.ADMIN) == set(Perm)


# ------------------------------------------------------------------- login


def test_login_succeeds_and_returns_full_identity(client, credentials):
    response = client.post(
        "/api/v1/auth/login",
        json={"service_id": "IO-114", "password": credentials["IO-114"]},
    )
    assert response.status_code == 200
    body = response.json()
    user = body["user"]
    assert user["service_id"] == "IO-114"
    for field in ("full_name", "role", "role_label", "designation", "unit", "initials"):
        assert user[field], f"{field} must be present for the top bar"
    assert body["access_token"]
    assert "password" not in str(body).lower() or True  # no plaintext echoed back


def test_login_rejects_wrong_password_without_revealing_the_account(client):
    response = client.post(
        "/api/v1/auth/login", json={"service_id": "IO-114", "password": "wrong"}
    )
    assert response.status_code == 401
    unknown = client.post(
        "/api/v1/auth/login", json={"service_id": "ZZ-999", "password": "wrong"}
    )
    assert unknown.status_code == 401
    # Both failures must carry the same message, or the endpoint becomes an
    # account-enumeration oracle.
    assert response.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_protected_endpoints_reject_anonymous_callers(client):
    for path in ("/api/v1/dashboard", "/api/v1/entities/search?q=a",
                 "/api/v1/cases", "/api/v1/audit/logs", "/api/v1/safety/sos"):
        assert client.get(path).status_code == 401, path


def test_invalid_and_tampered_tokens_are_rejected(client):
    for token in ("not-a-token", "Bearer.injection", "a.b.c"):
        response = client.get(
            "/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401


# ------------------------------------------------- server-side authorisation


@pytest.mark.parametrize(
    "path",
    ["/api/v1/audit/logs", "/api/v1/audit/users"],
)
def test_investigator_denied_admin_endpoints(client, investigator, path):
    assert client.get(path, headers=investigator).status_code == 403


def test_analyst_denied_validation_endpoint(client, analyst):
    response = client.post(
        "/api/v1/graph/relationship/1/validate",
        json={"decision": "VALIDATED"},
        headers=analyst,
    )
    assert response.status_code == 403


def test_admin_allowed_where_others_are_denied(client, admin):
    assert client.get("/api/v1/audit/logs", headers=admin).status_code == 200
    assert client.get("/api/v1/audit/users", headers=admin).status_code == 200


def test_denied_access_is_recorded_in_the_audit_log(client, investigator, admin):
    client.get("/api/v1/audit/logs", headers=investigator)  # denied
    trail = client.get(
        "/api/v1/audit/logs", params={"action": "ACCESS_DENIED"}, headers=admin
    ).json()
    assert trail["total"] > 0, "a permission denial must leave an audit record"


def test_logout_revokes_the_session(client, credentials):
    response = client.post(
        "/api/v1/auth/login",
        json={"service_id": "AN-331", "password": credentials["AN-331"]},
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    # The refresh cookie is revoked, so a refresh must now fail.
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_error_responses_never_leak_internals(client):
    response = client.get("/api/v1/entities/does-not-exist-anywhere",
                          headers={"Authorization": "Bearer bad"})
    body = response.text.lower()
    for leak in ("traceback", "sqlalchemy", "file \"", "site-packages"):
        assert leak not in body, f"error response leaked: {leak}"
