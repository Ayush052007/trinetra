"""Shared write helpers: uid allocation and audit logging."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Relationship, User


def next_relationship_uid(db: Session) -> str:
    """Allocate the next relationship uid.

    Derived from the current max rather than a running counter so it stays
    correct across process restarts and concurrent workers.
    """
    latest = db.scalar(select(func.max(Relationship.uid)))
    if latest and latest.startswith("r-") and latest[2:].isdigit():
        return f"r-{int(latest[2:]) + 1:06d}"
    count = db.scalar(select(func.count(Relationship.id))) or 0
    return f"r-{count + 1:06d}"


def record_audit(
    db: Session,
    *,
    action: str,
    user: User | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    case_id: int | None = None,
    result: str = "SUCCESS",
    detail: str | None = None,
    ip_address: str | None = None,
    actor_override: str | None = None,
) -> AuditLog:
    """Append an audit event.

    The actor name is denormalised so the trail stays readable even if the
    user record is later removed - an audit log that can lose its subject is
    not an audit log.
    """
    entry = AuditLog(
        timestamp=datetime.now(UTC),
        user_id=user.id if user else None,
        actor=actor_override or (f"{user.full_name} ({user.service_id})" if user else "system"),
        actor_role=user.role if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        case_id=case_id,
        result=result,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry


def audit_payload(entry: AuditLog) -> dict[str, Any]:
    return {
        "id": entry.id,
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        "actor": entry.actor,
        "actor_role": entry.actor_role,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "case_id": entry.case_id,
        "result": entry.result,
        "detail": entry.detail,
        "ip_address": entry.ip_address,
    }
