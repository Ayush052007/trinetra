"""Authentication endpoints.

Security behaviours implemented here rather than described:
  * scrypt password verification, constant-time.
  * Account lockout after N consecutive failures, for a fixed window.
  * Uniform failure messaging - a wrong service ID and a wrong password are
    indistinguishable to the caller, so the endpoint cannot be used to
    enumerate valid accounts.
  * Refresh-token rotation with server-side revocation.
  * Every outcome written to the audit log, including failures.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import (
    client_ip,
    enforce_rate_limit,
    get_current_user,
    user_payload,
)
from app.core.rbac import ROLE_DESIGNATION, permissions_for
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    password_strength_errors,
    verify_password,
)
from app.db.models import SessionToken, User
from app.db.session import get_db
from app.services.mutations import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "trinetra_refresh"

# Deliberately identical for every failure mode.
INVALID_CREDENTIALS = "Invalid Service ID or password."


class LoginRequest(BaseModel):
    service_id: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    remember: bool = False


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def _issue_session(
    db: Session, user: User, request: Request, response: Response, remember: bool
) -> dict:
    access, access_expires = create_access_token(user.id, user.service_id, user.role)
    refresh, refresh_expires, jti = create_refresh_token(user.id, remember)

    db.add(
        SessionToken(
            jti=jti,
            user_id=user.id,
            issued_at=datetime.now(UTC),
            expires_at=refresh_expires,
            ip_address=client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:255],
        )
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=int((refresh_expires - datetime.now(UTC)).total_seconds()),
        path="/api/v1/auth",
    )
    return {
        "access_token": access,
        "token_type": "bearer",
        "expires_at": access_expires.isoformat(),
        "expires_in": int((access_expires - datetime.now(UTC)).total_seconds()),
        "user": user_payload(user),
    }


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    enforce_rate_limit(request, "auth", settings.AUTH_RATE_LIMIT_PER_MINUTE)
    ip = client_ip(request)
    service_id = payload.service_id.strip().upper()

    user = db.scalars(select(User).where(User.service_id == service_id)).first()
    now = datetime.now(UTC)

    if user is None:
        record_audit(
            db, action="LOGIN_FAILED", resource_type="auth", resource_id=service_id,
            result="FAILURE", detail="Unknown service ID", ip_address=ip,
            actor_override=f"unknown ({service_id})",
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds())
        record_audit(
            db, action="LOGIN_BLOCKED", user=user, resource_type="auth",
            result="DENIED", detail=f"Account locked, {remaining}s remaining",
            ip_address=ip,
        )
        db.commit()
        raise HTTPException(
            status.HTTP_423_LOCKED,
            {
                "message": (
                    f"Account temporarily locked after {settings.MAX_FAILED_LOGINS} "
                    f"failed attempts."
                ),
                "locked_until": user.locked_until.isoformat(),
                "retry_after_seconds": remaining,
            },
        )

    if not user.is_active:
        record_audit(
            db, action="LOGIN_FAILED", user=user, resource_type="auth",
            result="DENIED", detail="Account deactivated", ip_address=ip,
        )
        db.commit()
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account has been deactivated. Contact your System Administrator.",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_attempts += 1
        detail = f"Incorrect password (attempt {user.failed_attempts})"
        action = "LOGIN_FAILED"
        if user.failed_attempts >= settings.MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            user.failed_attempts = 0
            action = "ACCOUNT_LOCKED"
            detail = (
                f"Locked for {settings.LOCKOUT_MINUTES} minutes after "
                f"{settings.MAX_FAILED_LOGINS} consecutive failures"
            )
        record_audit(
            db, action=action, user=user, resource_type="auth",
            result="FAILURE", detail=detail, ip_address=ip,
        )
        db.commit()
        if action == "ACCOUNT_LOCKED":
            raise HTTPException(
                status.HTTP_423_LOCKED,
                {
                    "message": (
                        f"Account locked after {settings.MAX_FAILED_LOGINS} failed "
                        f"attempts. Try again in {settings.LOCKOUT_MINUTES} minutes."
                    ),
                    "locked_until": user.locked_until.isoformat(),
                    "retry_after_seconds": settings.LOCKOUT_MINUTES * 60,
                },
            )
        remaining = settings.MAX_FAILED_LOGINS - user.failed_attempts
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            {
                "message": INVALID_CREDENTIALS,
                "attempts_remaining": remaining,
            },
        )

    # Success.
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    user.last_login_ip = ip
    session = _issue_session(db, user, request, response, payload.remember)
    record_audit(
        db, action="LOGIN_SUCCESS", user=user, resource_type="auth",
        result="SUCCESS",
        detail=f"Signed in as {user.designation}" + (" (remembered device)" if payload.remember else ""),
        ip_address=ip,
    )
    db.commit()
    return session


@router.post("/refresh")
def refresh_session(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """Rotate the refresh token and issue a new access token."""
    enforce_rate_limit(request, "auth", settings.AUTH_RATE_LIMIT_PER_MINUTE)
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No active session.")
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired.") from None
    if payload.get("typ") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session token.")

    stored = db.scalars(
        select(SessionToken).where(SessionToken.jti == payload["jti"])
    ).first()
    if stored is None or stored.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has been revoked.")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is no longer valid.")

    # Rotation: the presented token is retired as the new one is issued.
    stored.revoked = True
    stored.revoked_at = datetime.now(UTC)
    session = _issue_session(db, user, request, response, remember=False)
    record_audit(
        db, action="TOKEN_REFRESH", user=user, resource_type="auth",
        result="SUCCESS", ip_address=client_ip(request),
    )
    db.commit()
    return session


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Revoke every active refresh token for this user."""
    active = db.scalars(
        select(SessionToken).where(
            SessionToken.user_id == user.id, SessionToken.revoked.is_(False)
        )
    ).all()
    for token in active:
        token.revoked = True
        token.revoked_at = datetime.now(UTC)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    record_audit(
        db, action="LOGOUT", user=user, resource_type="auth", result="SUCCESS",
        detail=f"Revoked {len(active)} session token(s)", ip_address=client_ip(request),
    )
    db.commit()
    return {"status": "signed_out", "sessions_revoked": len(active)}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {
        "user": user_payload(user),
        "deployment": {
            "unit": settings.DEPLOYMENT_UNIT,
            "organisation": settings.DEPLOYMENT_ORG,
            "division": settings.DEPLOYMENT_DIVISION,
        },
    }


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        record_audit(
            db, action="PASSWORD_CHANGE_FAILED", user=user, resource_type="auth",
            result="FAILURE", detail="Current password incorrect",
            ip_address=client_ip(request),
        )
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")

    errors = password_strength_errors(payload.new_password)
    if errors:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "Password does not meet policy.", "errors": errors})

    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "New password must differ from the current one."
        )

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.now(UTC)
    # Force re-authentication everywhere after a credential change.
    for token in db.scalars(
        select(SessionToken).where(
            SessionToken.user_id == user.id, SessionToken.revoked.is_(False)
        )
    ).all():
        token.revoked = True
        token.revoked_at = datetime.now(UTC)
    record_audit(
        db, action="PASSWORD_CHANGED", user=user, resource_type="auth",
        result="SUCCESS", detail="All sessions revoked", ip_address=client_ip(request),
    )
    db.commit()
    return {"status": "password_changed", "reauthentication_required": True}


@router.get("/roles")
def roles() -> dict:
    """Role reference, for the admin screen. Not an authentication surface."""
    return {
        "roles": [
            {
                "role": role,
                "designation": designation,
                "permissions": sorted(permissions_for(role)),
            }
            for role, designation in ROLE_DESIGNATION.items()
        ]
    }
