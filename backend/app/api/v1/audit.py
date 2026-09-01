"""Audit log and administration."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import ROLE_DESIGNATION, Perm, permissions_for
from app.db.models import AuditLog, Case, SessionToken, User
from app.db.session import get_db
from app.services.mutations import audit_payload, record_audit

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(api_rate_limiter)])


@router.get("/logs")
def logs(
    action: str | None = None,
    actor: str | None = None,
    case_id: int | None = None,
    result: str | None = None,
    days: int | None = Query(None, ge=1, le=365),
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission(Perm.AUDIT_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor:
        stmt = stmt.where(AuditLog.actor.ilike(f"%{actor}%"))
    if case_id:
        stmt = stmt.where(AuditLog.case_id == case_id)
    if result:
        stmt = stmt.where(AuditLog.result == result.upper())
    if days:
        stmt = stmt.where(AuditLog.timestamp >= datetime.now(UTC) - timedelta(days=days))
    if q:
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(AuditLog.detail).like(pattern),
                func.lower(AuditLog.action).like(pattern),
                func.lower(AuditLog.actor).like(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    ).all()

    return {
        "items": [audit_payload(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
        "actions": [
            {"action": a, "count": n}
            for a, n in db.execute(
                select(AuditLog.action, func.count())
                .group_by(AuditLog.action).order_by(func.count().desc())
            ).all()
        ],
        "results": [
            {"result": r, "count": n}
            for r, n in db.execute(
                select(AuditLog.result, func.count()).group_by(AuditLog.result)
            ).all()
        ],
    }


@router.get("/logs/export")
def export_logs(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_permission(Perm.AUDIT_READ, Perm.DATA_EXPORT)),
    db: Session = Depends(get_db),
) -> Response:
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.timestamp >= datetime.now(UTC) - timedelta(days=days))
        .order_by(AuditLog.timestamp.desc())
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "timestamp", "actor", "role", "action", "resource_type",
        "resource_id", "case_id", "result", "detail", "ip_address",
    ])
    for row in rows:
        writer.writerow([
            row.timestamp.isoformat() if row.timestamp else "",
            row.actor, row.actor_role or "", row.action,
            row.resource_type or "", row.resource_id or "",
            row.case_id or "", row.result, row.detail or "", row.ip_address or "",
        ])

    record_audit(
        db, action="AUDIT_EXPORTED", user=user, resource_type="audit",
        detail=f"{len(rows)} entries over {days} days", ip_address=client_ip(request),
    )
    db.commit()

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="trinetra_audit_{stamp}.csv"'},
    )


@router.get("/users")
def users(
    user: User = Depends(require_permission(Perm.USER_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Department roster for the administration screen."""
    rows = db.scalars(select(User).order_by(User.service_id)).all()
    now = datetime.now(UTC)
    return {
        "items": [
            {
                "service_id": u.service_id,
                "full_name": u.full_name,
                "initials": u.initials,
                "role": u.role,
                "role_label": ROLE_DESIGNATION.get(u.role, u.role),
                "designation": u.designation,
                "unit": u.unit,
                "email": u.email,
                "extension": u.extension,
                "is_active": u.is_active,
                "is_locked": bool(u.locked_until and u.locked_until > now),
                "locked_until": u.locked_until.isoformat() if u.locked_until else None,
                "failed_attempts": u.failed_attempts,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "last_login_ip": u.last_login_ip,
                "permission_count": len(permissions_for(u.role)),
                "active_sessions": db.scalar(
                    select(func.count()).select_from(SessionToken).where(
                        SessionToken.user_id == u.id, SessionToken.revoked.is_(False)
                    )
                ) or 0,
            }
            for u in rows
        ]
    }


@router.post("/users/{service_id}/unlock")
def unlock_user(
    service_id: str,
    request: Request,
    user: User = Depends(require_permission(Perm.USER_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    target = db.scalars(select(User).where(User.service_id == service_id.upper())).first()
    if target is None:
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    target.locked_until = None
    target.failed_attempts = 0
    record_audit(
        db, action="ACCOUNT_UNLOCKED", user=user, resource_type="user",
        resource_id=target.service_id, detail=f"Unlocked by {user.service_id}",
        ip_address=client_ip(request),
    )
    db.commit()
    return {"service_id": target.service_id, "message": f"{target.full_name} unlocked."}
