"""Case management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import ROLE_DESIGNATION, Perm
from app.db.base import CaseStatus, EvidenceStatus, Priority
from app.db.models import (
    Case,
    CaseEntity,
    CaseMember,
    CaseNote,
    Entity,
    Evidence,
    Event,
    PriorityScore,
    Relationship,
    User,
)
from app.db.models_safety import Incident, SafetyAlert
from app.db.session import get_db
from app.services.mutations import record_audit

router = APIRouter(prefix="/cases", tags=["cases"], dependencies=[Depends(api_rate_limiter)])

VALID_TRANSITIONS = {
    CaseStatus.OPEN: {CaseStatus.UNDER_INVESTIGATION, CaseStatus.CLOSED},
    CaseStatus.UNDER_INVESTIGATION: {CaseStatus.REVIEW, CaseStatus.RESOLVED, CaseStatus.OPEN},
    CaseStatus.REVIEW: {CaseStatus.RESOLVED, CaseStatus.UNDER_INVESTIGATION},
    CaseStatus.RESOLVED: {CaseStatus.CLOSED, CaseStatus.REVIEW},
    CaseStatus.CLOSED: set(),
}


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=4000)
    module: str = Field("NETWORK", pattern="^(NETWORK|WOMEN_SAFETY)$")
    priority: str = Field("MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")


class CaseUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=4000)
    status: str | None = None
    priority: str | None = Field(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class EntityLink(BaseModel):
    entity_uid: str
    role_in_case: str | None = Field(None, max_length=48)


class AssignRequest(BaseModel):
    service_id: str
    role_on_case: str = Field("Contributor", max_length=48)


def _case_or_404(db: Session, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")
    return case


@router.get("")
def list_cases(
    status_filter: str | None = Query(None, alias="status"),
    module: str | None = None,
    user: User = Depends(require_permission(Perm.CASE_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Case)
    if status_filter == "active":
        stmt = stmt.where(Case.status != CaseStatus.CLOSED)
    elif status_filter:
        stmt = stmt.where(Case.status == status_filter.upper())
    if module:
        stmt = stmt.where(Case.module == module)

    cases = db.scalars(stmt.order_by(Case.opened_at.desc())).all()
    items = []
    for case in cases:
        items.append({
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
            "description": case.description,
            "status": case.status,
            "priority": case.priority,
            "module": case.module,
            "classification": case.data_classification,
            "owner": case.owner.full_name if case.owner else None,
            "owner_service_id": case.owner.service_id if case.owner else None,
            "opened_at": case.opened_at.isoformat() if case.opened_at else None,
            "closed_at": case.closed_at.isoformat() if case.closed_at else None,
            "entity_count": db.scalar(
                select(func.count()).select_from(CaseEntity).where(CaseEntity.case_id == case.id)
            ) or 0,
            "relationship_count": db.scalar(
                select(func.count()).select_from(Relationship).where(Relationship.case_id == case.id)
            ) or 0,
            "pending_validation": db.scalar(
                select(func.count()).select_from(Relationship).where(
                    Relationship.case_id == case.id,
                    Relationship.evidence_status == EvidenceStatus.INFERRED,
                )
            ) or 0,
        })
    return {
        "items": items,
        "statuses": [s.value for s in CaseStatus],
        "count": len(items),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    request: Request,
    user: User = Depends(require_permission(Perm.CASE_CREATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    year = datetime.now(UTC).year
    prefix = "WS" if payload.module == "WOMEN_SAFETY" else "NX"
    existing = db.scalar(
        select(func.count()).select_from(Case).where(Case.module == payload.module)
    ) or 0
    case = Case(
        case_number=f"{prefix}-{year}-{existing + 1:04d}",
        title=payload.title,
        description=payload.description,
        status=CaseStatus.OPEN,
        priority=payload.priority,
        module=payload.module,
        owner_id=user.id,
        opened_at=datetime.now(UTC),
    )
    db.add(case)
    db.flush()
    db.add(
        CaseMember(
            case_id=case.id, user_id=user.id,
            role_on_case="Lead Investigator", assigned_at=datetime.now(UTC),
        )
    )
    record_audit(
        db, action="CASE_CREATED", user=user, resource_type="case",
        resource_id=case.case_number, case_id=case.id, detail=case.title,
        ip_address=client_ip(request),
    )
    db.commit()
    return {"id": case.id, "case_number": case.case_number, "title": case.title}


@router.get("/{case_id}")
def case_detail(
    case_id: int,
    request: Request,
    user: User = Depends(require_permission(Perm.CASE_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = _case_or_404(db, case_id)

    entity_rows = db.execute(
        select(Entity, CaseEntity)
        .join(CaseEntity, CaseEntity.entity_id == Entity.id)
        .where(CaseEntity.case_id == case.id)
    ).all()

    scores = {
        s.entity_id: s
        for s in db.scalars(
            select(PriorityScore).where(
                PriorityScore.entity_id.in_([e.id for e, _ in entity_rows]) if entity_rows else False
            )
        ).all()
    }

    relationships = db.scalars(
        select(Relationship).where(Relationship.case_id == case.id)
    ).all()

    record_audit(
        db, action="CASE_OPENED", user=user, resource_type="case",
        resource_id=case.case_number, case_id=case.id, detail=case.title,
        ip_address=client_ip(request),
    )
    db.commit()

    return {
        "id": case.id,
        "case_number": case.case_number,
        "title": case.title,
        "description": case.description,
        "status": case.status,
        "priority": case.priority,
        "module": case.module,
        "classification": case.data_classification,
        "owner": case.owner.full_name if case.owner else None,
        "opened_at": case.opened_at.isoformat() if case.opened_at else None,
        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
        "allowed_transitions": sorted(VALID_TRANSITIONS.get(case.status, set())),
        "team": [
            {
                "service_id": m.user.service_id,
                "name": m.user.full_name,
                "role": m.user.role,
                "role_label": ROLE_DESIGNATION.get(m.user.role, m.user.role),
                "role_on_case": m.role_on_case,
            }
            for m in db.scalars(
                select(CaseMember).where(CaseMember.case_id == case.id)
            ).all()
        ],
        "entities": [
            {
                "uid": entity.uid, "name": entity.name, "type": entity.type,
                "role_in_case": link.role_in_case,
                "priority_score": round(scores[entity.id].score, 1) if entity.id in scores else None,
                "priority_band": scores[entity.id].band if entity.id in scores else None,
            }
            for entity, link in entity_rows
        ],
        "counts": {
            "entities": len(entity_rows),
            "relationships": len(relationships),
            "observed": sum(1 for r in relationships if r.evidence_status == EvidenceStatus.OBSERVED),
            "inferred": sum(1 for r in relationships if r.evidence_status == EvidenceStatus.INFERRED),
            "validated": sum(1 for r in relationships if r.evidence_status == EvidenceStatus.VALIDATED),
            "rejected": sum(1 for r in relationships if r.evidence_status == EvidenceStatus.REJECTED),
            "events": db.scalar(
                select(func.count()).select_from(Event).where(Event.case_id == case.id)
            ) or 0,
            "evidence": db.scalar(
                select(func.count()).select_from(Evidence).where(Evidence.case_id == case.id)
            ) or 0,
            "incidents": db.scalar(
                select(func.count()).select_from(Incident).where(Incident.case_id == case.id)
            ) or 0,
            "alerts": db.scalar(
                select(func.count()).select_from(SafetyAlert).where(SafetyAlert.case_id == case.id)
            ) or 0,
        },
        "notes": [
            {
                "id": n.id, "body": n.body,
                "author": n.author.full_name if n.author else None,
                "created_at": n.created_at.isoformat(),
            }
            for n in sorted(case.notes, key=lambda n: n.created_at, reverse=True)
        ],
    }


@router.patch("/{case_id}")
def update_case(
    case_id: int,
    payload: CaseUpdate,
    request: Request,
    user: User = Depends(require_permission(Perm.CASE_UPDATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = _case_or_404(db, case_id)
    changes: list[str] = []

    if payload.status and payload.status != case.status:
        target = payload.status.upper()
        if target not in VALID_TRANSITIONS.get(case.status, set()):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                {
                    "message": f"Cannot move a case from {case.status} to {target}.",
                    "allowed": sorted(VALID_TRANSITIONS.get(case.status, set())),
                },
            )
        if target == CaseStatus.CLOSED:
            from app.core.rbac import permissions_for

            if Perm.CASE_CLOSE not in permissions_for(user.role):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Closing a case requires Supervisory Officer authority.",
                )
            case.closed_at = datetime.now(UTC)
        changes.append(f"status {case.status} -> {target}")
        case.status = target

    for field in ("title", "description", "priority"):
        value = getattr(payload, field)
        if value is not None and value != getattr(case, field):
            changes.append(f"{field} updated")
            setattr(case, field, value)

    if changes:
        record_audit(
            db, action="CASE_UPDATED", user=user, resource_type="case",
            resource_id=case.case_number, case_id=case.id,
            detail="; ".join(changes), ip_address=client_ip(request),
        )
    db.commit()
    return {"id": case.id, "status": case.status, "changes": changes}


@router.post("/{case_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(
    case_id: int,
    payload: NoteCreate,
    request: Request,
    user: User = Depends(require_permission(Perm.CASE_UPDATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = _case_or_404(db, case_id)
    note = CaseNote(case_id=case.id, author_id=user.id, body=payload.body)
    db.add(note)
    db.flush()
    record_audit(
        db, action="CASE_NOTE_ADDED", user=user, resource_type="case",
        resource_id=case.case_number, case_id=case.id,
        detail=payload.body[:120], ip_address=client_ip(request),
    )
    db.commit()
    return {
        "id": note.id, "body": note.body, "author": user.full_name,
        "created_at": note.created_at.isoformat(),
    }


@router.post("/{case_id}/entities")
def add_entity(
    case_id: int,
    payload: EntityLink,
    request: Request,
    user: User = Depends(require_permission(Perm.CASE_UPDATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = _case_or_404(db, case_id)
    entity = db.scalars(select(Entity).where(Entity.uid == payload.entity_uid)).first()
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    existing = db.scalars(
        select(CaseEntity).where(
            CaseEntity.case_id == case.id, CaseEntity.entity_id == entity.id
        )
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Entity is already linked to this case.")

    db.add(
        CaseEntity(
            case_id=case.id, entity_id=entity.id, role_in_case=payload.role_in_case,
            added_at=datetime.now(UTC), added_by_id=user.id,
        )
    )
    record_audit(
        db, action="CASE_ENTITY_ADDED", user=user, resource_type="case",
        resource_id=case.case_number, case_id=case.id,
        detail=f"{entity.name} ({entity.type})", ip_address=client_ip(request),
    )
    db.commit()
    return {"case_id": case.id, "entity_uid": entity.uid, "message": f"{entity.name} added to case."}


@router.delete("/{case_id}/entities/{entity_uid}")
def remove_entity(
    case_id: int,
    entity_uid: str,
    request: Request,
    user: User = Depends(require_permission(Perm.CASE_UPDATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = _case_or_404(db, case_id)
    entity = db.scalars(select(Entity).where(Entity.uid == entity_uid)).first()
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    link = db.scalars(
        select(CaseEntity).where(
            CaseEntity.case_id == case.id, CaseEntity.entity_id == entity.id
        )
    ).first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity is not linked to this case.")
    db.delete(link)
    record_audit(
        db, action="CASE_ENTITY_REMOVED", user=user, resource_type="case",
        resource_id=case.case_number, case_id=case.id,
        detail=entity.name, ip_address=client_ip(request),
    )
    db.commit()
    return {"message": f"{entity.name} removed from case."}


@router.post("/{case_id}/assign")
def assign(
    case_id: int,
    payload: AssignRequest,
    request: Request,
    user: User = Depends(require_permission(Perm.CASE_ASSIGN)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = _case_or_404(db, case_id)
    member = db.scalars(
        select(User).where(User.service_id == payload.service_id.upper())
    ).first()
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such team member.")
    existing = db.scalars(
        select(CaseMember).where(
            CaseMember.case_id == case.id, CaseMember.user_id == member.id
        )
    ).first()
    if existing:
        existing.role_on_case = payload.role_on_case
    else:
        db.add(
            CaseMember(
                case_id=case.id, user_id=member.id,
                role_on_case=payload.role_on_case, assigned_at=datetime.now(UTC),
            )
        )
    record_audit(
        db, action="CASE_ASSIGNED", user=user, resource_type="case",
        resource_id=case.case_number, case_id=case.id,
        detail=f"{member.full_name} as {payload.role_on_case}",
        ip_address=client_ip(request),
    )
    db.commit()
    return {"message": f"{member.full_name} assigned as {payload.role_on_case}."}
