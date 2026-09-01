"""The dashboard aggregate.

One call returns every widget on the command centre. Each block carries the
route its click-through leads to, plus the filter state to apply on arrival,
so a widget is genuinely a doorway into the detail page rather than a
decorative summary that happens to sit near a link.

Every number here is a query result. Nothing is constant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import api_rate_limiter, get_current_user
from app.core.rbac import Perm, permissions_for
from app.db.base import AlertStatus, CaseStatus, EvidenceStatus, SosStatus
from app.db.models import (
    Case,
    CaseEntity,
    Entity,
    Event,
    Notification,
    PriorityScore,
    Record,
    Relationship,
    ResolutionCandidate,
    User,
)
from app.db.models_safety import (
    Incident,
    IncidentType,
    PatternDetection,
    SafetyAlert,
    SosAlert,
)
from app.db.session import get_db
from app.services import graph_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(api_rate_limiter)])


def _count(db: Session, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    for clause in where:
        stmt = stmt.where(clause)
    return db.scalar(stmt) or 0


@router.get("")
def dashboard(
    case_id: int | None = Query(None, description="Scope the dashboard to one case"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    granted = permissions_for(user.role)

    cases = db.scalars(select(Case).order_by(Case.opened_at.desc())).all()
    active_case = next((c for c in cases if c.id == case_id), None) if case_id else None
    scope_entity_ids: list[int] | None = None
    if active_case:
        scope_entity_ids = list(
            db.scalars(
                select(CaseEntity.entity_id).where(CaseEntity.case_id == active_case.id)
            ).all()
        )

    # ---------------------------------------------------------- KPI tiles
    total_records = _count(db, Record)
    recent_records = _count(db, Record, Record.created_at >= week_ago)
    total_entities = _count(db, Entity, Entity.is_active.is_(True))
    recent_entities = _count(
        db, Entity, Entity.is_active.is_(True), Entity.created_at >= week_ago
    )
    total_relationships = _count(
        db, Relationship, Relationship.evidence_status != EvidenceStatus.REJECTED
    )
    active_cases = _count(db, Case, Case.status != CaseStatus.CLOSED)
    pending_leads = _count(
        db, Relationship, Relationship.evidence_status == EvidenceStatus.INFERRED
    ) + _count(db, ResolutionCandidate, ResolutionCandidate.status == "PENDING")

    def pct(recent: int, total: int) -> float | None:
        prior = total - recent
        return round(recent / prior * 100, 1) if prior > 0 and recent else None

    kpis = [
        {
            "key": "records", "label": "Total Records", "value": total_records,
            "delta_pct": pct(recent_records, total_records),
            "caption": f"{recent_records:,} added in the last 7 days" if recent_records else "Ingested source records",
            "route": "/data-management", "filters": {},
        },
        {
            "key": "entities", "label": "Entities Extracted", "value": total_entities,
            "delta_pct": pct(recent_entities, total_entities),
            "caption": "People, phones, vehicles, organisations and more",
            "route": "/data-management", "filters": {"tab": "entities"},
        },
        {
            "key": "relationships", "label": "Relationships Found", "value": total_relationships,
            "delta_pct": None,
            "caption": f"{_count(db, Relationship, Relationship.evidence_status == EvidenceStatus.OBSERVED):,} observed, "
                       f"{_count(db, Relationship, Relationship.evidence_status.in_([EvidenceStatus.INFERRED, EvidenceStatus.VALIDATED])):,} inferred or validated",
            "route": "/network", "filters": {},
        },
        {
            "key": "cases", "label": "Active Cases", "value": active_cases,
            "delta_pct": None,
            "caption": f"{_count(db, Case, Case.module == 'WOMEN_SAFETY')} in the Women Safety module",
            "route": "/cases", "filters": {"status": "active"},
        },
        {
            "key": "leads", "label": "Pending Leads", "value": pending_leads,
            "delta_pct": None,
            "caption": "Inferred links and match candidates awaiting review",
            "route": "/link-analysis", "filters": {"status": "pending"},
        },
    ]

    # ------------------------------------------- investigation priority
    # Scoped to the selected case when one is active: a global ranking would
    # bury a case's own subjects beneath unrelated high-degree records.
    priority_query = (
        select(PriorityScore, Entity)
        .join(Entity, PriorityScore.entity_id == Entity.id)
        .where(Entity.type == "person", Entity.is_active.is_(True))
    )
    if scope_entity_ids:
        priority_query = priority_query.where(Entity.id.in_(scope_entity_ids))
    priority_rows = db.execute(
        priority_query.order_by(PriorityScore.score.desc()).limit(6)
    ).all()

    top_priority = []
    for score_row, entity in priority_rows:
        factors = sorted(score_row.factors, key=lambda f: -f.get("contribution", 0))
        top_priority.append({
            "entity_uid": entity.uid,
            "name": entity.name,
            "score": round(score_row.score, 1),
            "band": score_row.band,
            "confidence": score_row.confidence,
            "top_factor": factors[0]["label"] if factors else None,
            "top_factor_detail": factors[0]["detail"] if factors else None,
            "route": f"/entity/{entity.uid}",
            "filters": {"panel": "priority"},
        })

    # ----------------------------------------------------------- alerts
    alert_rows = db.scalars(
        select(SafetyAlert)
        .where(SafetyAlert.status != AlertStatus.RESOLVED)
        .order_by(SafetyAlert.raised_at.desc())
        .limit(6)
    ).all()
    alerts = [
        {
            "alert_ref": a.alert_ref,
            "priority": a.priority,
            "status": a.status,
            "message": a.message,
            "module": a.module,
            "raised_at": a.raised_at.isoformat() if a.raised_at else None,
            "time_label": a.time_label,
            "route": "/safety/alerts",
            "filters": {"alert": a.alert_ref},
        }
        for a in alert_rows
    ]

    # --------------------------------------------------------- timeline
    timeline_query = select(Event).where(Event.occurred_at.is_not(None))
    if active_case:
        timeline_query = timeline_query.where(Event.case_id == active_case.id)
    timeline_rows = db.scalars(
        timeline_query.order_by(Event.occurred_at.desc()).limit(8)
    ).all()
    timeline = [
        {
            "uid": e.uid,
            "type": e.type,
            "title": e.title,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            "time_label": e.time_label,
            "route": "/timeline",
            "filters": {"event": e.uid},
        }
        for e in sorted(timeline_rows, key=lambda e: e.occurred_at or now)
    ]

    # ---------------------------------------------------------- geography
    from app.services.safety import build_heatmap

    heatmap = build_heatmap(db)
    zones = [
        {
            "zone_ref": z["zone_ref"],
            "name": z["name"],
            "band": z["band"],
            "incident_count": z["incident_count"],
            "weighted_density": z["weighted_density"],
            "center": z["center"],
            "radius_km": z["radius_km"],
            "route": "/safety/heatmap",
            "filters": {"zone": z["zone_ref"]},
        }
        for z in heatmap["zones"]
    ]

    # ------------------------------------------------------ women safety
    sos_by_status = {
        status_value: _count(db, SosAlert, SosAlert.status == status_value)
        for status_value in (
            SosStatus.RECEIVED, SosStatus.ASSIGNED, SosStatus.RESPONDING, SosStatus.RESOLVED
        )
    }
    incidents_by_type = dict(
        db.execute(
            select(Incident.type, func.count())
            .group_by(Incident.type)
            .order_by(func.count().desc())
        ).all()
    )
    women_safety = {
        "sos": {
            "by_status": sos_by_status,
            "open": sum(v for k, v in sos_by_status.items() if k != SosStatus.RESOLVED),
            "route": "/safety/sos",
        },
        "incidents": {
            "total": _count(db, Incident),
            "by_type": [
                {"key": k, "label": IncidentType.LABELS.get(k, k), "count": v}
                for k, v in incidents_by_type.items()
            ],
            "critical": _count(db, Incident, Incident.priority == "CRITICAL"),
            "route": "/safety/incidents",
        },
        "patterns": {
            "pending": _count(
                db, PatternDetection, PatternDetection.status == "PENDING_REVIEW"
            ),
            "total": _count(db, PatternDetection),
            "route": "/safety/patterns",
        },
    }

    # -------------------------------------------------- pending actions
    pending_actions: list[dict[str, Any]] = []
    if Perm.RELATIONSHIP_VALIDATE in granted:
        inferred_query = (
            select(Relationship)
            .where(Relationship.evidence_status == EvidenceStatus.INFERRED)
            .order_by(Relationship.confidence.desc())
        )
        if active_case:
            inferred_query = inferred_query.where(Relationship.case_id == active_case.id)
        for rel in db.scalars(inferred_query.limit(5)).all():
            source = db.get(Entity, rel.source_id)
            target = db.get(Entity, rel.target_id)
            pending_actions.append({
                "kind": "hidden_link",
                "id": rel.id,
                "title": f"{source.name if source else '?'} - {target.name if target else '?'}",
                "subtitle": (rel.derivation or {}).get("reason", "Inferred connection")[:160],
                "confidence": round(rel.confidence, 3),
                "evidence_status": rel.evidence_status,
                "route": "/link-analysis",
                "filters": {"relationship": rel.id},
            })
    if Perm.RESOLUTION_DECIDE in granted:
        for candidate in db.scalars(
            select(ResolutionCandidate)
            .where(ResolutionCandidate.status == "PENDING")
            .order_by(ResolutionCandidate.confidence.desc())
            .limit(4)
        ).all():
            a = db.get(Entity, candidate.entity_a_id)
            b = db.get(Entity, candidate.entity_b_id)
            pending_actions.append({
                "kind": "resolution",
                "id": candidate.id,
                "title": f"{a.name if a else '?'} / {b.name if b else '?'}",
                "subtitle": "Possible duplicate or alias identity",
                "confidence": round(candidate.confidence, 3),
                "evidence_status": "INFERRED",
                "route": "/entity-resolution",
                "filters": {"candidate": candidate.id},
            })
    pending_actions.sort(key=lambda a: -a["confidence"])

    # ------------------------------------------------------ recent records
    record_rows = db.scalars(
        select(Record).order_by(Record.created_at.desc()).limit(10)
    ).all()
    recent_record_rows = [
        {
            "id": r.id,
            "source_type": r.source_type,
            "source_ref": r.source_ref,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "summary": _summarise_record(db, r),
            "classification": r.data_classification,
            "route": "/data-management",
            "filters": {"record": r.id},
        }
        for r in record_rows
    ]

    # ------------------------------------------------------------ graph
    if active_case:
        graph_preview = graph_service.case_subgraph(db, active_case.id, limit=60)
    else:
        lead = db.scalars(
            select(Entity).where(Entity.uid == "p1", Entity.is_active.is_(True))
        ).first()
        graph_preview = (
            graph_service.subgraph_payload(db, lead.uid, depth=2)
            if lead
            else {"nodes": [], "edges": [], "counts": {}}
        )

    snapshot = graph_service.get_graph(db).snapshot()

    notifications = db.scalars(
        select(Notification)
        .where(
            Notification.read.is_(False),
            (Notification.user_id == user.id) | (Notification.role_target == user.role)
            | (Notification.role_target.is_(None) & Notification.user_id.is_(None)),
        )
        .order_by(Notification.created_at.desc())
        .limit(10)
    ).all()

    return {
        "generated_at": now.isoformat(),
        "scope": {
            "case_id": active_case.id if active_case else None,
            "case_number": active_case.case_number if active_case else None,
            "case_title": active_case.title if active_case else None,
            "label": active_case.case_number if active_case else "All cases",
        },
        "cases": [
            {
                "id": c.id, "case_number": c.case_number, "title": c.title,
                "status": c.status, "priority": c.priority, "module": c.module,
            }
            for c in cases
        ],
        "kpis": kpis,
        "graph_preview": graph_preview,
        "graph_totals": {
            "nodes": snapshot.node_count,
            "edges": snapshot.edge_count,
        },
        "top_priority": top_priority,
        "alerts": alerts,
        "timeline": timeline,
        "zones": zones,
        "women_safety": women_safety,
        "pending_actions": pending_actions[:6],
        "recent_records": recent_record_rows,
        "notifications": [
            {
                "id": n.id, "title": n.title, "body": n.body,
                "severity": n.severity, "link": n.link,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "role_view": {
            "role": user.role,
            "emphasis": (
                "women_safety" if user.role == "WOMEN_SAFETY_OFFICER"
                else "administration" if user.role == "ADMIN"
                else "analysis" if user.role == "ANALYST"
                else "investigation"
            ),
            "can_validate": Perm.RELATIONSHIP_VALIDATE in granted,
            "can_resolve": Perm.RESOLUTION_DECIDE in granted,
            "can_dispatch": Perm.SAFETY_DISPATCH in granted,
            "can_read_audit": Perm.AUDIT_READ in granted,
        },
    }


def _summarise_record(db: Session, record: Record) -> str:
    payload = record.payload or {}
    source_uid = payload.get("source")
    target_uid = payload.get("target")
    relation = payload.get("relationship", "")
    if source_uid and target_uid:
        source = db.scalars(select(Entity).where(Entity.uid == source_uid)).first()
        target = db.scalars(select(Entity).where(Entity.uid == target_uid)).first()
        if source and target:
            return f"{source.name} - {relation.replace('_', ' ').lower()} - {target.name}"
    return record.source_ref or "Source record"


@router.get("/system")
def system_panel(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Administrator panel: health, ingestion and audit summary."""
    from app.config import settings
    from app.db.models import AuditLog, IngestionJob

    now = datetime.now(UTC)
    day_ago = now - timedelta(days=1)
    return {
        "graph_backend": settings.GRAPH_BACKEND,
        "database": settings.DATABASE_URL.split("://")[0],
        "environment": settings.ENVIRONMENT,
        "classification": settings.DATA_CLASSIFICATION,
        "users_total": _count(db, User),
        "users_active": _count(db, User, User.is_active.is_(True)),
        "audit_events_24h": _count(db, AuditLog, AuditLog.timestamp >= day_ago),
        "failed_logins_24h": _count(
            db, AuditLog, AuditLog.timestamp >= day_ago,
            AuditLog.action.in_(["LOGIN_FAILED", "ACCOUNT_LOCKED"]),
        ),
        "access_denied_24h": _count(
            db, AuditLog, AuditLog.timestamp >= day_ago, AuditLog.action == "ACCESS_DENIED"
        ),
        "ingestion_jobs": _count(db, IngestionJob),
        "locked_accounts": _count(db, User, User.locked_until.is_not(None)),
    }
