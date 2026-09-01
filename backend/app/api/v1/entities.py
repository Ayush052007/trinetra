"""Entity search and profiles."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import Perm
from app.db.base import EvidenceStatus
from app.db.models import (
    Case,
    CaseEntity,
    Entity,
    EntityAlias,
    Evidence,
    Event,
    PriorityScore,
    Relationship,
    User,
)
from app.db.models_safety import Incident
from app.db.session import get_db
from app.services import graph_service
from app.services.mutations import record_audit
from app.services.priority import score_payload

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "ai"))
from trinetra_nlp.engine import normalize  # noqa: E402

router = APIRouter(prefix="/entities", tags=["entities"], dependencies=[Depends(api_rate_limiter)])

TYPE_LABELS = {
    "person": "Person", "phone": "Phone", "location": "Location",
    "organization": "Organization", "vehicle": "Vehicle",
    "transaction": "Transaction", "social": "Social Handle",
    "event": "Event", "case_record": "Prior Case",
}


@router.get("/search")
def search(
    request: Request,
    q: str = Query("", max_length=120),
    types: str | None = Query(None, description="Comma-separated entity types"),
    case_id: int | None = None,
    limit: int = Query(25, ge=1, le=100),
    user: User = Depends(require_permission(Perm.ENTITY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Search names and aliases across the live database."""
    query = (q or "").strip()
    if not query:
        return {"query": "", "results": [], "count": 0}

    pattern = f"%{query.lower()}%"

    # Normalisation is type-specific, so a single normalised form cannot match
    # every stored record. Build one variant per identifier convention and
    # match on any of them - otherwise "98765 43210" fails to find the phone
    # stored as "9876543210", which is exactly how an investigator types it.
    variants = {normalize(query)}
    for entity_type in ("phone", "vehicle", "transaction"):
        candidate = normalize(query, entity_type)
        if candidate:
            variants.add(candidate)
    variants = {v for v in variants if len(v) >= 2}

    def matches_any(column):
        return or_(*[column.like(f"%{v}%") for v in variants])

    alias_matches = select(EntityAlias.entity_id).where(
        or_(
            func.lower(EntityAlias.alias).like(pattern),
            matches_any(EntityAlias.normalized_alias),
        )
    )
    stmt = (
        select(Entity)
        .where(
            Entity.is_active.is_(True),
            or_(
                func.lower(Entity.name).like(pattern),
                matches_any(Entity.normalized_name),
                Entity.uid == query,
                Entity.id.in_(alias_matches),
            ),
        )
    )
    if types:
        stmt = stmt.where(Entity.type.in_([t.strip() for t in types.split(",") if t.strip()]))
    if case_id:
        stmt = stmt.where(
            Entity.id.in_(select(CaseEntity.entity_id).where(CaseEntity.case_id == case_id))
        )

    rows = db.scalars(stmt.limit(limit * 3)).all()

    snapshot = graph_service.get_graph(db).snapshot()
    scores = {
        s.entity_id: s
        for s in db.scalars(
            select(PriorityScore).where(
                PriorityScore.entity_id.in_([r.id for r in rows]) if rows else False
            )
        ).all()
    }

    def relevance(entity: Entity) -> tuple:
        name = entity.name.lower()
        exact = name == query.lower()
        starts = name.startswith(query.lower())
        return (not exact, not starts, len(entity.name))

    results = []
    for entity in sorted(rows, key=relevance)[:limit]:
        score = scores.get(entity.id)
        results.append({
            "uid": entity.uid,
            "name": entity.name,
            "type": entity.type,
            "type_label": TYPE_LABELS.get(entity.type, entity.type),
            "aliases": [a.alias for a in entity.aliases],
            "connections": len(snapshot.adjacency.get(entity.uid, {})),
            "priority_score": round(score.score, 1) if score else None,
            "priority_band": score.band if score else None,
            "classification": entity.data_classification,
            "attributes": entity.attributes or {},
        })

    record_audit(
        db, action="ENTITY_SEARCH", user=user, resource_type="search",
        resource_id=query[:60], detail=f"{len(results)} result(s)",
        ip_address=client_ip(request),
    )
    db.commit()
    return {"query": query, "results": results, "count": len(results)}


@router.get("/{uid}")
def profile(
    uid: str,
    request: Request,
    user: User = Depends(require_permission(Perm.ENTITY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Full entity profile: relationships, cases, timeline, evidence, priority."""
    entity = db.scalars(select(Entity).where(Entity.uid == uid)).first()
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No entity found with id '{uid}'.")

    snapshot = graph_service.get_graph(db).snapshot()
    neighbours = snapshot.adjacency.get(uid, {})

    relationships = db.scalars(
        select(Relationship).where(
            or_(Relationship.source_id == entity.id, Relationship.target_id == entity.id),
            Relationship.evidence_status != EvidenceStatus.REJECTED,
        )
    ).all()

    related_ids = {
        r.target_id if r.source_id == entity.id else r.source_id for r in relationships
    }
    related = {
        e.id: e for e in db.scalars(select(Entity).where(Entity.id.in_(related_ids))).all()
    }

    grouped: dict[str, list[dict]] = {}
    relationship_rows = []
    for rel in relationships:
        other = related.get(r_id := (rel.target_id if rel.source_id == entity.id else rel.source_id))
        if other is None:
            continue
        item = {
            "relationship_id": rel.id,
            "uid": rel.uid,
            "type": rel.type,
            "direction": "outgoing" if rel.source_id == entity.id else "incoming",
            "other": {
                "uid": other.uid, "name": other.name, "type": other.type,
                "type_label": TYPE_LABELS.get(other.type, other.type),
            },
            "evidence_status": rel.evidence_status,
            "is_observed": rel.evidence_status in (EvidenceStatus.OBSERVED, EvidenceStatus.VALIDATED),
            "confidence": round(rel.confidence, 3),
            "source_ref": rel.source,
            "occurred_at": rel.occurred_at.isoformat() if rel.occurred_at else None,
            "time_label": rel.time_label,
            "attributes": rel.attributes or {},
            "derivation": rel.derivation or {},
        }
        relationship_rows.append(item)
        grouped.setdefault(other.type, []).append(item)

    case_rows = db.execute(
        select(Case).join(CaseEntity, CaseEntity.case_id == Case.id)
        .where(CaseEntity.entity_id == entity.id)
    ).scalars().all()

    events = db.scalars(
        select(Event).where(Event.entity_id == entity.id)
        .order_by(Event.occurred_at.asc()).limit(100)
    ).all()

    evidence = db.scalars(
        select(Evidence).where(Evidence.entity_id == entity.id).limit(50)
    ).all()

    incidents = db.scalars(
        select(Incident).where(
            or_(
                Incident.subject_entity_id == entity.id,
                Incident.location_entity_id == entity.id,
            )
        )
    ).all()

    score = db.scalars(
        select(PriorityScore).where(PriorityScore.entity_id == entity.id)
        .order_by(PriorityScore.computed_at.desc())
    ).first()

    record_audit(
        db, action="ENTITY_VIEWED", user=user, resource_type="entity",
        resource_id=uid, detail=entity.name, ip_address=client_ip(request),
    )
    db.commit()

    return {
        "uid": entity.uid,
        "name": entity.name,
        "type": entity.type,
        "type_label": TYPE_LABELS.get(entity.type, entity.type),
        "aliases": [a.alias for a in entity.aliases],
        "attributes": entity.attributes or {},
        "source": entity.source,
        "classification": entity.data_classification,
        "is_active": entity.is_active,
        "merged_into": (
            db.get(Entity, entity.merged_into_id).uid if entity.merged_into_id else None
        ),
        "coordinates": (
            {"lat": entity.latitude, "lng": entity.longitude}
            if entity.latitude is not None else None
        ),
        "summary": {
            "connections": len(neighbours),
            "relationships": len(relationship_rows),
            "observed": sum(1 for r in relationship_rows if r["is_observed"]),
            "inferred": sum(1 for r in relationship_rows if not r["is_observed"]),
            "cases": len(case_rows),
            "events": len(events),
            "evidence": len(evidence),
            "incidents": len(incidents),
            "locations": len(grouped.get("location", [])),
            "organizations": len(grouped.get("organization", [])),
            "transactions": len(grouped.get("transaction", [])),
            "phones": len(grouped.get("phone", [])),
            "vehicles": len(grouped.get("vehicle", [])),
        },
        "relationships": relationship_rows,
        "relationships_by_type": {
            k: sorted(v, key=lambda r: -r["confidence"]) for k, v in grouped.items()
        },
        "cases": [
            {"id": c.id, "case_number": c.case_number, "title": c.title,
             "status": c.status, "module": c.module}
            for c in case_rows
        ],
        "timeline": [
            {
                "uid": e.uid, "type": e.type, "title": e.title,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                "time_label": e.time_label, "relationship_id": e.relationship_id,
            }
            for e in events
        ],
        "evidence": [
            {
                "evidence_ref": e.evidence_ref, "source": e.source,
                "source_type": e.source_type, "description": e.description,
                "status": e.status, "confidence": e.confidence,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in evidence
        ],
        "incidents": [
            {
                "incident_ref": i.incident_ref, "type": i.type, "priority": i.priority,
                "status": i.status, "description": i.description,
                "occurred_at": i.occurred_at.isoformat() if i.occurred_at else None,
            }
            for i in incidents
        ],
        "priority": score_payload(score, entity) if score else None,
    }


@router.get("")
def list_entities(
    type: str | None = None,
    case_id: int | None = None,
    q: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission(Perm.ENTITY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Paged entity listing for the Data Management table."""
    stmt = select(Entity).where(Entity.is_active.is_(True))
    count_stmt = select(func.count()).select_from(Entity).where(Entity.is_active.is_(True))
    if type:
        stmt = stmt.where(Entity.type == type)
        count_stmt = count_stmt.where(Entity.type == type)
    if q:
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(Entity.name).like(pattern))
        count_stmt = count_stmt.where(func.lower(Entity.name).like(pattern))
    if case_id:
        subquery = select(CaseEntity.entity_id).where(CaseEntity.case_id == case_id)
        stmt = stmt.where(Entity.id.in_(subquery))
        count_stmt = count_stmt.where(Entity.id.in_(subquery))

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Entity.type, Entity.name).offset(offset).limit(limit)).all()
    snapshot = graph_service.get_graph(db).snapshot()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "types": [
            {"key": t, "label": TYPE_LABELS.get(t, t), "count": n}
            for t, n in db.execute(
                select(Entity.type, func.count())
                .where(Entity.is_active.is_(True))
                .group_by(Entity.type).order_by(func.count().desc())
            ).all()
        ],
        "items": [
            {
                "uid": e.uid, "name": e.name, "type": e.type,
                "type_label": TYPE_LABELS.get(e.type, e.type),
                "aliases": [a.alias for a in e.aliases],
                "connections": len(snapshot.adjacency.get(e.uid, {})),
                "classification": e.data_classification,
                "source": e.source,
            }
            for e in rows
        ],
    }
