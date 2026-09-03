"""Knowledge-graph exploration, hidden-link discovery and validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import Perm
from app.db.base import EvidenceStatus
from app.db.models import Entity, Evidence, Relationship, User, Validation
from app.db.session import get_db
from app.services import discovery, graph_service
from app.services.mutations import next_relationship_uid, record_audit

router = APIRouter(prefix="/graph", tags=["graph"], dependencies=[Depends(api_rate_limiter)])


class RelationshipCreate(BaseModel):
    source_uid: str
    target_uid: str
    type: str = Field(min_length=1, max_length=48)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    source_ref: str | None = Field(None, max_length=200)
    case_id: int | None = None
    note: str | None = Field(None, max_length=1000)


class ValidationRequest(BaseModel):
    decision: str = Field(pattern="^(VALIDATED|REJECTED|UNDER_REVIEW)$")
    rationale: str | None = Field(None, max_length=2000)


@router.get("/neighbourhood/{uid}")
def neighbourhood(
    uid: str,
    depth: int = Query(1, ge=1, le=3),
    include_inferred: bool = True,
    types: str | None = None,
    user: User = Depends(require_permission(Perm.GRAPH_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    entity = db.scalars(select(Entity).where(Entity.uid == uid)).first()
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No entity found with id '{uid}'.")
    type_list = [t.strip() for t in types.split(",")] if types else None
    return graph_service.subgraph_payload(db, uid, depth, include_inferred, type_list)


@router.get("/case/{case_id}")
def case_graph(
    case_id: int,
    limit: int = Query(150, ge=10, le=500),
    user: User = Depends(require_permission(Perm.GRAPH_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return graph_service.case_subgraph(db, case_id, limit)


@router.get("/path")
def path(
    source: str,
    target: str,
    max_length: int = Query(4, ge=1, le=6),
    user: User = Depends(require_permission(Perm.GRAPH_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return discovery.path_between(db, source, target, max_length)


@router.get("/common")
def common(
    a: str,
    b: str,
    user: User = Depends(require_permission(Perm.GRAPH_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"a": a, "b": b, "shared": discovery.common_connections(db, a, b)}


@router.get("/hidden-links")
def hidden_links(
    case_id: int | None = None,
    limit: int = Query(25, ge=1, le=100),
    min_confidence: float = Query(0.35, ge=0.0, le=1.0),
    user: User = Depends(require_permission(Perm.GRAPH_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Candidate connections discovered by analysis, plus stored inferred links."""
    discovered = discovery.discover_hidden_links(db, case_id, limit, min_confidence)

    stored_query = select(Relationship).where(
        Relationship.evidence_status.in_(
            [EvidenceStatus.INFERRED, EvidenceStatus.UNDER_REVIEW,
             EvidenceStatus.VALIDATED, EvidenceStatus.REJECTED]
        )
    )
    if case_id:
        stored_query = stored_query.where(Relationship.case_id == case_id)

    # Load the links and their endpoints in one query, then batch-load the
    # supporting records. Walking these with db.get() per row is a handful of
    # round-trips each - unnoticeable locally, ~12 seconds against a remote
    # database.
    stored_rows = db.scalars(
        stored_query.order_by(Relationship.confidence.desc()).options(
            joinedload(Relationship.source_entity),
            joinedload(Relationship.target_entity),
        )
    ).all()

    supporting_ids: set[int] = set()
    for rel in stored_rows:
        supporting_ids.update((rel.derivation or {}).get("supporting_relationship_ids", []))
    support_map = {
        r.id: r
        for r in db.scalars(
            select(Relationship)
            .where(Relationship.id.in_(supporting_ids))
            .options(
                joinedload(Relationship.source_entity),
                joinedload(Relationship.target_entity),
            )
        )
    } if supporting_ids else {}

    stored = []
    for rel in stored_rows:
        source = rel.source_entity
        target = rel.target_entity
        if not source or not target:
            continue
        derivation = rel.derivation or {}
        supporting = []
        for rid in derivation.get("supporting_relationship_ids", []):
            support = support_map.get(rid)
            if support is None:
                continue
            s_source = support.source_entity
            s_target = support.target_entity
            supporting.append({
                "relationship_id": support.id,
                "description": (
                    f"{s_source.name if s_source else '?'} - "
                    f"{support.type.replace('_', ' ')} - "
                    f"{s_target.name if s_target else '?'}"
                ),
                "source_ref": support.source,
                "evidence_status": support.evidence_status,
                "confidence": round(support.confidence, 3),
                "occurred_at": support.occurred_at.isoformat() if support.occurred_at else None,
            })
        stored.append({
            "relationship_id": rel.id,
            "uid": rel.uid,
            "source": {"uid": source.uid, "name": source.name, "type": source.type},
            "target": {"uid": target.uid, "name": target.name, "type": target.type},
            "type": rel.type,
            "evidence_status": rel.evidence_status,
            "confidence": round(rel.confidence, 3),
            "reason": derivation.get("reason"),
            "method": derivation.get("method"),
            "factors": derivation.get("factors", []),
            "supporting": supporting,
            "case_id": rel.case_id,
            "validated_at": rel.validated_at.isoformat() if rel.validated_at else None,
            "requires_validation": rel.evidence_status == EvidenceStatus.INFERRED,
            "disclaimer": (
                "Inferred relationship. Not an observed fact and not evidence of "
                "wrongdoing. Requires authorised investigator validation."
            ),
        })

    return {
        "stored": stored,
        "discovered": discovered,
        "counts": {
            "stored": len(stored),
            "discovered": len(discovered),
            "pending_validation": sum(1 for s in stored if s["requires_validation"]),
        },
    }


@router.get("/relationship/{relationship_id}/evidence")
def relationship_evidence(
    relationship_id: int,
    request: Request,
    user: User = Depends(require_permission(Perm.GRAPH_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Everything supporting one assertion - the 'View Evidence' payload."""
    rel = db.get(Relationship, relationship_id)
    if rel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship not found.")
    source = db.get(Entity, rel.source_id)
    target = db.get(Entity, rel.target_id)

    evidence_rows = db.scalars(
        select(Evidence).where(Evidence.relationship_id == rel.id)
    ).all()

    derivation = rel.derivation or {}
    supporting = []
    for rid in derivation.get("supporting_relationship_ids", []):
        support = db.get(Relationship, rid)
        if support is None:
            continue
        s_source = db.get(Entity, support.source_id)
        s_target = db.get(Entity, support.target_id)
        support_evidence = db.scalars(
            select(Evidence).where(Evidence.relationship_id == support.id)
        ).all()
        supporting.append({
            "relationship_id": support.id,
            "source": {"uid": s_source.uid, "name": s_source.name} if s_source else None,
            "target": {"uid": s_target.uid, "name": s_target.name} if s_target else None,
            "type": support.type,
            "evidence_status": support.evidence_status,
            "confidence": round(support.confidence, 3),
            "source_ref": support.source,
            "occurred_at": support.occurred_at.isoformat() if support.occurred_at else None,
            "evidence": [
                {"evidence_ref": e.evidence_ref, "source": e.source,
                 "source_type": e.source_type, "description": e.description}
                for e in support_evidence
            ],
        })

    validations = db.scalars(
        select(Validation).where(
            Validation.target_type == "relationship", Validation.target_id == rel.id
        ).order_by(Validation.timestamp.desc())
    ).all()

    record_audit(
        db, action="EVIDENCE_VIEWED", user=user, resource_type="relationship",
        resource_id=rel.id, case_id=rel.case_id,
        detail=f"{source.name if source else '?'} - {rel.type} - {target.name if target else '?'}",
        ip_address=client_ip(request),
    )
    db.commit()

    return {
        "relationship_id": rel.id,
        "source": {"uid": source.uid, "name": source.name, "type": source.type} if source else None,
        "target": {"uid": target.uid, "name": target.name, "type": target.type} if target else None,
        "type": rel.type,
        "evidence_status": rel.evidence_status,
        "is_observed": rel.evidence_status in (EvidenceStatus.OBSERVED, EvidenceStatus.VALIDATED),
        "confidence": round(rel.confidence, 3),
        "source_ref": rel.source,
        "occurred_at": rel.occurred_at.isoformat() if rel.occurred_at else None,
        "time_label": rel.time_label,
        "attributes": rel.attributes or {},
        "reason": derivation.get("reason"),
        "method": derivation.get("method"),
        "factors": derivation.get("factors", []),
        "direct_evidence": [
            {
                "evidence_ref": e.evidence_ref, "source": e.source,
                "source_type": e.source_type, "description": e.description,
                "status": e.status, "confidence": e.confidence,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in evidence_rows
        ],
        "supporting_relationships": supporting,
        "validation_history": [
            {
                "decision": v.decision,
                "previous_status": v.previous_status,
                "rationale": v.rationale,
                "timestamp": v.timestamp.isoformat() if v.timestamp else None,
                "by": db.get(User, v.user_id).full_name if db.get(User, v.user_id) else None,
            }
            for v in validations
        ],
    }


@router.post("/relationship/{relationship_id}/validate")
def validate_relationship(
    relationship_id: int,
    payload: ValidationRequest,
    request: Request,
    user: User = Depends(require_permission(Perm.RELATIONSHIP_VALIDATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record an investigator decision on an inferred relationship.

    The decision changes the stored evidence status, which propagates to the
    graph projection, the dashboard counters and every downstream analytic.
    """
    rel = db.get(Relationship, relationship_id)
    if rel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship not found.")

    if rel.evidence_status == EvidenceStatus.OBSERVED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This relationship is directly observed in source records and does not "
            "require validation.",
        )

    previous = rel.evidence_status
    rel.evidence_status = payload.decision
    rel.validated_by_id = user.id
    rel.validated_at = datetime.now(UTC)

    db.add(
        Validation(
            timestamp=datetime.now(UTC),
            user_id=user.id,
            target_type="relationship",
            target_id=rel.id,
            decision=payload.decision,
            previous_status=previous,
            rationale=payload.rationale,
        )
    )
    for evidence in db.scalars(
        select(Evidence).where(Evidence.relationship_id == rel.id)
    ).all():
        evidence.status = payload.decision

    source = db.get(Entity, rel.source_id)
    target = db.get(Entity, rel.target_id)
    record_audit(
        db,
        action=f"RELATIONSHIP_{payload.decision}",
        user=user, resource_type="relationship", resource_id=rel.id,
        case_id=rel.case_id,
        detail=(
            f"{source.name if source else '?'} - {rel.type} - "
            f"{target.name if target else '?'} : {previous} -> {payload.decision}"
            + (f" | {payload.rationale}" if payload.rationale else "")
        ),
        ip_address=client_ip(request),
    )
    db.commit()
    graph_service.invalidate()

    return {
        "relationship_id": rel.id,
        "previous_status": previous,
        "evidence_status": rel.evidence_status,
        "validated_by": user.full_name,
        "validated_at": rel.validated_at.isoformat(),
        "message": (
            f"Relationship marked {payload.decision.replace('_', ' ').lower()}. "
            "The knowledge graph and all dependent analytics have been updated."
        ),
    }


@router.post("/relationship")
def create_relationship(
    payload: RelationshipCreate,
    request: Request,
    user: User = Depends(require_permission(Perm.RELATIONSHIP_CREATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Manually record a relationship observed by an investigator."""
    source = db.scalars(select(Entity).where(Entity.uid == payload.source_uid)).first()
    target = db.scalars(select(Entity).where(Entity.uid == payload.target_uid)).first()
    if source is None or target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source or target entity not found.")
    if source.id == target.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "An entity cannot be related to itself."
        )

    rel = Relationship(
        uid=next_relationship_uid(db),
        source_id=source.id,
        target_id=target.id,
        type=payload.type,
        # Investigator-entered relationships are observations, recorded as such.
        evidence_status=EvidenceStatus.OBSERVED,
        confidence=payload.confidence,
        source=payload.source_ref or f"Investigator entry ({user.service_id})",
        occurred_at=datetime.now(UTC),
        case_id=payload.case_id,
        derivation={"reason": payload.note} if payload.note else {},
        validated_by_id=user.id,
        validated_at=datetime.now(UTC),
    )
    db.add(rel)
    db.flush()

    record_audit(
        db, action="RELATIONSHIP_CREATED", user=user, resource_type="relationship",
        resource_id=rel.id, case_id=payload.case_id,
        detail=f"{source.name} - {payload.type} - {target.name}",
        ip_address=client_ip(request),
    )
    db.commit()
    graph_service.invalidate()
    return {
        "relationship_id": rel.id,
        "uid": rel.uid,
        "message": "Relationship recorded and added to the knowledge graph.",
    }
