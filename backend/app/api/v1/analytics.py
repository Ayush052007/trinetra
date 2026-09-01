"""Graph analytics, priority scoring and the investigation timeline.

Every figure returned here is computed from the live graph or database at
request time. Where an analysis is not implemented, it is absent - the API
never reports a metric it did not calculate.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import Perm
from app.db.base import EvidenceStatus
from app.db.models import (
    Case,
    CaseEntity,
    Entity,
    Event,
    PriorityScore,
    Relationship,
    User,
)
from app.db.session import get_db
from app.services import graph_service, priority
from app.services.mutations import record_audit
from app.services.priority import score_payload

router = APIRouter(tags=["analytics"], dependencies=[Depends(api_rate_limiter)])

ENTITY_TYPE_LABELS = {
    "person": "Person", "phone": "Phone", "location": "Location",
    "organization": "Organization", "vehicle": "Vehicle",
    "transaction": "Transaction", "social": "Social Handle",
    "event": "Event", "case_record": "Prior Case",
}


@router.get("/analytics/overview")
def overview(
    entity_type: str | None = Query(None, description="Restrict rankings to one entity type"),
    case_id: int | None = None,
    user: User = Depends(require_permission(Perm.ANALYTICS_RUN)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Centrality, communities, components and structural summary."""
    repo = graph_service.get_graph(db)
    snapshot = repo.snapshot()
    if not snapshot.nodes:
        return {"empty": True, "message": "The knowledge graph contains no entities yet."}

    scope: set[str] | None = None
    if case_id:
        entity_ids = db.scalars(
            select(CaseEntity.entity_id).where(CaseEntity.case_id == case_id)
        ).all()
        scope = set(
            db.scalars(select(Entity.uid).where(Entity.id.in_(entity_ids))).all()
        )

    analytics = graph_service.graph_analytics(db)
    centrality = analytics["centrality"]
    communities = analytics["communities"]
    modularity = analytics["modularity"]
    components = analytics["components"]

    def eligible(uid: str) -> bool:
        node = snapshot.nodes.get(uid)
        if node is None:
            return False
        if entity_type and node.type != entity_type:
            return False
        return scope is None or uid in scope

    def rank(measure: str, limit: int = 10) -> list[dict[str, Any]]:
        values = centrality[measure]
        ordered = sorted(
            (u for u in values if eligible(u)), key=lambda u: -values[u]
        )[:limit]
        return [
            {
                "uid": u,
                "name": snapshot.nodes[u].name,
                "type": snapshot.nodes[u].type,
                "value": round(values[u], 5),
                "connections": len(snapshot.adjacency.get(u, {})),
            }
            for u in ordered
        ]

    community_sizes = Counter(communities.values())
    largest = [
        {
            "community": community_id,
            "size": size,
            "members": [
                {"uid": u, "name": snapshot.nodes[u].name, "type": snapshot.nodes[u].type}
                for u in sorted(
                    (u for u, c in communities.items() if c == community_id),
                    key=lambda u: -len(snapshot.adjacency.get(u, {})),
                )[:8]
            ],
        }
        for community_id, size in community_sizes.most_common(8)
    ]

    type_counts = Counter(n.type for n in snapshot.nodes.values())
    relationship_counts = Counter(e.type for e in snapshot.edges.values())

    return {
        "empty": False,
        "graph": {
            "nodes": snapshot.node_count,
            "edges": snapshot.edge_count,
            "backend": repo.backend_name(),
            "density": round(
                (2 * snapshot.edge_count)
                / max(1, snapshot.node_count * (snapshot.node_count - 1)),
                6,
            ),
        },
        "centrality": {
            "degree": {
                "label": "Degree centrality",
                "description": "Entities with the most direct connections.",
                "top": rank("degree"),
            },
            "betweenness": {
                "label": "Betweenness centrality",
                "description": (
                    "Entities that sit on the most shortest paths between others - "
                    "structural brokers between otherwise separate groups."
                ),
                "top": rank("betweenness"),
                "exact": analytics["betweenness_exact"],
                "note": analytics["betweenness_note"],
            },
            "closeness": {
                "label": "Closeness centrality",
                "description": "Entities with the shortest average distance to all others.",
                "top": rank("closeness"),
            },
        },
        "communities": {
            "label": "Community detection (Louvain)",
            "description": (
                "Clusters of entities more densely connected to each other than to "
                "the rest of the network."
            ),
            "count": len(community_sizes),
            "modularity": round(modularity, 4),
            "modularity_note": (
                "Modularity above 0.3 indicates genuinely separated clusters rather "
                "than an arbitrary partition."
            ),
            "largest": largest,
        },
        "components": {
            "label": "Connected components",
            "count": len(components),
            "largest_size": len(components[0]) if components else 0,
            "isolated": sum(1 for c in components if len(c) == 1),
        },
        "composition": {
            "entity_types": [
                {"key": t, "label": ENTITY_TYPE_LABELS.get(t, t), "count": n}
                for t, n in type_counts.most_common()
            ],
            "relationship_types": [
                {"key": t, "label": t.replace("_", " ").title(), "count": n}
                for t, n in relationship_counts.most_common(12)
            ],
        },
        "evidence_split": {
            "observed": sum(1 for e in snapshot.edges.values() if e.is_observed),
            "inferred": sum(1 for e in snapshot.edges.values() if not e.is_observed),
        },
        "computed_at": datetime.now(UTC).isoformat(),
    }


@router.get("/analytics/priority")
def priority_ranking(
    case_id: int | None = None,
    entity_type: str = Query("person"),
    band: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission(Perm.ANALYTICS_RUN)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = (
        select(PriorityScore, Entity)
        .join(Entity, PriorityScore.entity_id == Entity.id)
        .where(Entity.is_active.is_(True))
    )
    if entity_type:
        stmt = stmt.where(Entity.type == entity_type)
    if band:
        stmt = stmt.where(PriorityScore.band == band)
    if case_id:
        entity_ids = select(CaseEntity.entity_id).where(CaseEntity.case_id == case_id)
        stmt = stmt.where(Entity.id.in_(entity_ids))

    rows = db.execute(
        stmt.order_by(PriorityScore.score.desc()).offset(offset).limit(limit)
    ).all()

    band_counts = dict(
        db.execute(
            select(PriorityScore.band, func.count())
            .join(Entity, PriorityScore.entity_id == Entity.id)
            .where(Entity.type == entity_type if entity_type else True)
            .group_by(PriorityScore.band)
        ).all()
    )

    return {
        "items": [score_payload(score, entity) for score, entity in rows],
        "band_counts": band_counts,
        "weights": priority.WEIGHTS,
        "algorithm_version": priority.ALGORITHM_VERSION,
        "disclaimer": (
            "Investigation Priority Score ranks records by how prominently they "
            "feature in the available data. It is not a measure of guilt, "
            "criminality or involvement in any offence."
        ),
    }


@router.post("/analytics/priority/recompute")
def recompute_priority(
    request: Request,
    case_id: int | None = None,
    user: User = Depends(require_permission(Perm.PRIORITY_RECOMPUTE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = priority.compute_scores(db, case_id)
    record_audit(
        db, action="PRIORITY_RECOMPUTED", user=user, resource_type="analytics",
        case_id=case_id, detail=f"{len(rows)} score(s) recomputed",
        ip_address=client_ip(request),
    )
    db.commit()
    return {
        "recomputed": len(rows),
        "algorithm_version": priority.ALGORITHM_VERSION,
        "computed_at": datetime.now(UTC).isoformat(),
    }


@router.get("/timeline")
def timeline(
    case_id: int | None = None,
    entity_uid: str | None = None,
    types: str | None = Query(None, description="Comma-separated event types"),
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    user: User = Depends(require_permission(Perm.CASE_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Chronological events, each resolving back to its underlying record."""
    stmt = select(Event)
    if case_id:
        stmt = stmt.where(Event.case_id == case_id)
    if entity_uid:
        entity = db.scalars(select(Entity).where(Entity.uid == entity_uid)).first()
        if entity:
            stmt = stmt.where(
                or_(Event.entity_id == entity.id, Event.location_id == entity.id)
            )
    if types:
        stmt = stmt.where(Event.type.in_([t.strip() for t in types.split(",") if t.strip()]))
    if date_from:
        try:
            stmt = stmt.where(Event.occurred_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            stmt = stmt.where(Event.occurred_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    rows = db.scalars(stmt.order_by(Event.occurred_at.asc()).limit(limit)).all()

    available_types = [
        {"key": t, "label": t.replace("_", " ").title(), "count": n}
        for t, n in db.execute(
            select(Event.type, func.count())
            .where(Event.case_id == case_id if case_id else True)
            .group_by(Event.type).order_by(func.count().desc())
        ).all()
    ]

    items = []
    for event in rows:
        entity = db.get(Entity, event.entity_id) if event.entity_id else None
        location = db.get(Entity, event.location_id) if event.location_id else None
        items.append({
            "uid": event.uid,
            "type": event.type,
            "type_label": event.type.replace("_", " ").title(),
            "title": event.title,
            "description": event.description,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "time_label": event.time_label,
            "entity": {"uid": entity.uid, "name": entity.name, "type": entity.type} if entity else None,
            "location": {"uid": location.uid, "name": location.name} if location else None,
            "relationship_id": event.relationship_id,
            "incident_id": event.incident_id,
            "case_id": event.case_id,
            "classification": event.data_classification,
        })

    return {
        "items": items,
        "count": len(items),
        "available_types": available_types,
        "range": {
            "from": items[0]["occurred_at"] if items else None,
            "to": items[-1]["occurred_at"] if items else None,
        },
    }
