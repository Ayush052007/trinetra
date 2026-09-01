"""Request dependencies: authentication, authorisation, rate limiting.

require_permission() is the single enforcement point for RBAC. Every
non-public route depends on it. The frontend also hides controls the user
cannot use, but that is a usability affordance - this module is the boundary.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.rbac import ROLE_DESIGNATION, permissions_for
from app.core.security import decode_token
from app.db.models import SessionToken, User
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ------------------------------------------------------------ rate limiting

_buckets: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Sliding-window limiter. Returns False when the caller is over budget.

    In-process only: adequate for a single-worker deployment, and documented
    in docs/SECURITY.md as needing a shared store behind multiple workers.
    """
    now = time.monotonic()
    bucket = _buckets[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def enforce_rate_limit(request: Request, scope: str, limit: int) -> None:
    if not rate_limit(f"{scope}:{client_ip(request)}", limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment and try again.",
        )


def api_rate_limiter(request: Request) -> None:
    enforce_rate_limit(request, "api", settings.API_RATE_LIMIT_PER_MINUTE)


# ------------------------------------------------------------ current user


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the bearer token to an active user."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Please sign in.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise unauthorized
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer", "X-Session-Expired": "true"},
        ) from None
    except jwt.PyJWTError:
        raise unauthorized from None

    if payload.get("typ") != "access":
        raise unauthorized

    user = db.get(User, int(payload.get("sub", 0)))
    if user is None or not user.is_active:
        raise unauthorized

    request.state.user = user
    return user


def user_payload(user: User, permissions: set[str] | None = None) -> dict:
    """The identity block the UI renders in the top bar and profile menu."""
    perms = permissions if permissions is not None else permissions_for(user.role)
    return {
        "id": user.id,
        "service_id": user.service_id,
        "full_name": user.full_name,
        "initials": user.initials,
        "role": user.role,
        "role_label": ROLE_DESIGNATION.get(user.role, user.role),
        "designation": user.designation,
        "unit": user.unit,
        "email": user.email,
        "extension": user.extension,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "must_change_password": user.must_change_password,
        "permissions": sorted(perms),
    }


# ------------------------------------------------------------ authorisation


def require_permission(*required: str) -> Callable[..., User]:
    """Dependency factory enforcing that the caller holds every permission.

    Denials are recorded in the audit log: an attempt to reach a restricted
    endpoint is exactly the kind of event an audit trail exists for.
    """

    def dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        granted = permissions_for(user.role)
        missing = [p for p in required if p not in granted]
        if missing:
            from app.services.mutations import record_audit

            record_audit(
                db,
                action="ACCESS_DENIED",
                user=user,
                resource_type="endpoint",
                resource_id=request.url.path,
                result="DENIED",
                detail=f"Missing permission(s): {', '.join(missing)}",
                ip_address=client_ip(request),
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your role ({ROLE_DESIGNATION.get(user.role, user.role)}) does not "
                    f"have permission to perform this action."
                ),
            )
        return user

    return dependency


def require_role(*roles: str) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not have access to this area.",
            )
        return user

    return dependency
