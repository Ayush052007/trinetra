"""Entity resolution review queue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import Perm
from app.db.models import Entity, ResolutionCandidate, User, Validation
from app.db.session import get_db
from app.services import discovery, graph_service
from app.services.discovery import candidate_payload
from app.services.mutations import record_audit

router = APIRouter(
    prefix="/resolution", tags=["entity-resolution"], dependencies=[Depends(api_rate_limiter)]
)


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|REJECTED|UNDER_REVIEW)$")
    rationale: str | None = Field(None, max_length=2000)


@router.get("/candidates")
def candidates(
    status_filter: str = Query("PENDING", alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission(Perm.ENTITY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(ResolutionCandidate)
    if status_filter and status_filter.upper() != "ALL":
        stmt = stmt.where(ResolutionCandidate.status == status_filter.upper())

    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0
    rows = db.scalars(
        stmt.order_by(ResolutionCandidate.confidence.desc()).offset(offset).limit(limit)
    ).all()

    # Load every referenced entity and its aliases up front. Fetching them per
    # candidate is four round-trips each, which is invisible against a local
    # file and roughly 30 seconds against a remote database.
    entity_ids = {r.entity_a_id for r in rows} | {r.entity_b_id for r in rows}
    entities = {
        e.id: e
        for e in db.scalars(
            select(Entity)
            .where(Entity.id.in_(entity_ids))
            .options(selectinload(Entity.aliases))
        )
    } if entity_ids else {}

    items = []
    for row in rows:
        a = entities.get(row.entity_a_id)
        b = entities.get(row.entity_b_id)
        if a and b:
            items.append(candidate_payload(row, a, b))

    counts = dict(
        db.execute(
            select(ResolutionCandidate.status, func.count()).group_by(
                ResolutionCandidate.status
            )
        ).all()
    )
    return {"items": items, "total": total, "status_counts": counts}


@router.post("/refresh")
def refresh(
    request: Request,
    user: User = Depends(require_permission(Perm.RESOLUTION_DECIDE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    created = discovery.refresh_resolution_candidates(db)
    record_audit(
        db, action="RESOLUTION_REFRESHED", user=user, resource_type="resolution",
        detail=f"{created} new candidate(s)", ip_address=client_ip(request),
    )
    db.commit()
    return {"new_candidates": created}


@router.post("/candidates/{candidate_id}/decide")
def decide(
    candidate_id: int,
    payload: DecisionRequest,
    request: Request,
    user: User = Depends(require_permission(Perm.RESOLUTION_DECIDE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Accept, reject or defer a proposed identity match.

    Accepting links the two records with a VALIDATED alias_of relationship and
    deactivates the absorbed record. It is reversible: merged_into_id preserves
    where the record went and the original row is retained.
    """
    candidate = db.get(ResolutionCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match candidate not found.")
    if candidate.status != "PENDING":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This candidate has already been marked {candidate.status.lower()}.",
        )

    a = db.get(Entity, candidate.entity_a_id)
    b = db.get(Entity, candidate.entity_b_id)
    previous = candidate.status
    candidate.status = payload.decision
    candidate.decided_by_id = user.id
    candidate.decided_at = datetime.now(UTC)

    db.add(
        Validation(
            timestamp=datetime.now(UTC),
            user_id=user.id,
            target_type="resolution",
            target_id=candidate.id,
            decision=payload.decision,
            previous_status=previous,
            rationale=payload.rationale,
        )
    )

    merged_relationship_id = None
    if payload.decision == "ACCEPTED":
        edge = discovery.apply_merge(db, candidate, user.id)
        merged_relationship_id = edge.id

    record_audit(
        db,
        action=f"RESOLUTION_{payload.decision}",
        user=user, resource_type="resolution_candidate", resource_id=candidate.id,
        detail=(
            f"{a.name if a else '?'} / {b.name if b else '?'} "
            f"(confidence {candidate.confidence:.2f})"
            + (f" | {payload.rationale}" if payload.rationale else "")
        ),
        ip_address=client_ip(request),
    )
    db.commit()
    graph_service.invalidate()

    message = {
        "ACCEPTED": (
            "Identities merged. An alias relationship has been recorded and the "
            "absorbed record is now inactive. This can be reversed."
        ),
        "REJECTED": "Match rejected. These records will remain separate and will not be proposed again.",
        "UNDER_REVIEW": "Marked for further review.",
    }[payload.decision]

    return {
        "candidate_id": candidate.id,
        "decision": payload.decision,
        "merged_relationship_id": merged_relationship_id,
        "message": message,
    }
