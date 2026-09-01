"""Case report generation - preview, PDF and JSON export.

A report is compiled from stored case data at generation time and the compiled
snapshot is persisted, so a report remains a faithful record of what the case
looked like when it was produced.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import ROLE_DESIGNATION, Perm
from app.db.base import EvidenceStatus
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
    Report,
    User,
    Validation,
)
from app.db.models_safety import Incident, PatternDetection, SafetyAlert, SosAlert
from app.db.session import get_db
from app.services import graph_service
from app.services.mutations import record_audit

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(api_rate_limiter)])

DISCLAIMER = (
    "This report was compiled by TRINETRA, an investigative decision-support "
    "system, from the records held in the platform at the time of generation. "
    "Relationships marked INFERRED are analytical suggestions, not established "
    "facts, and carry no evidentiary weight unless independently corroborated. "
    "TRINETRA does not determine guilt and does not replace authorised human "
    "judgement. All findings require verification by an authorised investigator."
)


def compile_report(db: Session, case: Case, generated_by: User) -> dict[str, Any]:
    """Assemble the full case snapshot from stored data."""
    entity_rows = db.execute(
        select(Entity, CaseEntity)
        .join(CaseEntity, CaseEntity.entity_id == Entity.id)
        .where(CaseEntity.case_id == case.id)
    ).all()
    entity_ids = [e.id for e, _ in entity_rows]

    relationships = db.scalars(
        select(Relationship).where(Relationship.case_id == case.id)
    ).all()
    entity_by_id = {e.id: e for e, _ in entity_rows}
    for rel in relationships:
        for rid in (rel.source_id, rel.target_id):
            if rid not in entity_by_id:
                found = db.get(Entity, rid)
                if found:
                    entity_by_id[rid] = found

    scores = {
        s.entity_id: s
        for s in db.scalars(
            select(PriorityScore).where(PriorityScore.entity_id.in_(entity_ids))
        ).all()
    } if entity_ids else {}

    events = db.scalars(
        select(Event).where(Event.case_id == case.id).order_by(Event.occurred_at.asc())
    ).all()
    evidence = db.scalars(select(Evidence).where(Evidence.case_id == case.id)).all()
    incidents = db.scalars(select(Incident).where(Incident.case_id == case.id)).all()
    alerts = db.scalars(select(SafetyAlert).where(SafetyAlert.case_id == case.id)).all()
    sos_alerts = db.scalars(select(SosAlert).where(SosAlert.case_id == case.id)).all()
    detections = db.scalars(
        select(PatternDetection).where(PatternDetection.case_id == case.id)
    ).all()
    notes = db.scalars(select(CaseNote).where(CaseNote.case_id == case.id)).all()
    members = db.scalars(select(CaseMember).where(CaseMember.case_id == case.id)).all()

    validations = db.scalars(
        select(Validation).where(
            Validation.target_type == "relationship",
            Validation.target_id.in_([r.id for r in relationships]) if relationships else False,
        )
    ).all()

    # Network findings, computed over the case subgraph only.
    repo = graph_service.get_graph(db)
    snapshot = repo.snapshot()
    case_uids = {e.uid for e, _ in entity_rows}
    centrality = graph_service.graph_analytics(db)["centrality"]
    ranked = sorted(
        (u for u in case_uids if u in snapshot.nodes),
        key=lambda u: -centrality["degree"].get(u, 0),
    )[:8]

    def rel_line(rel: Relationship) -> dict[str, Any]:
        source = entity_by_id.get(rel.source_id)
        target = entity_by_id.get(rel.target_id)
        return {
            "id": rel.id,
            "source": source.name if source else "?",
            "target": target.name if target else "?",
            "type": rel.type.replace("_", " ").title(),
            "evidence_status": rel.evidence_status,
            "confidence": round(rel.confidence, 3),
            "source_ref": rel.source,
            "occurred_at": rel.occurred_at.isoformat() if rel.occurred_at else None,
            "time_label": rel.time_label,
            "reason": (rel.derivation or {}).get("reason"),
        }

    observed = [r for r in relationships if r.evidence_status == EvidenceStatus.OBSERVED]
    validated = [r for r in relationships if r.evidence_status == EvidenceStatus.VALIDATED]
    inferred = [r for r in relationships if r.evidence_status == EvidenceStatus.INFERRED]
    rejected = [r for r in relationships if r.evidence_status == EvidenceStatus.REJECTED]

    return {
        "meta": {
            "report_generated_at": datetime.now(UTC).isoformat(),
            "generated_by": {
                "name": generated_by.full_name,
                "service_id": generated_by.service_id,
                "designation": generated_by.designation,
                "unit": generated_by.unit,
            },
            "platform": f"{settings.APP_NAME} v{settings.VERSION}",
            "data_classification": case.data_classification,
            "classification_notice": (
                "SYNTHETIC DATA - generated and fictional records for demonstration "
                "and testing. This report contains no operational police data."
            ) if case.data_classification == "SYNTHETIC" else None,
        },
        "case": {
            "case_number": case.case_number,
            "title": case.title,
            "description": case.description,
            "status": case.status,
            "priority": case.priority,
            "module": case.module,
            "owner": case.owner.full_name if case.owner else None,
            "opened_at": case.opened_at.isoformat() if case.opened_at else None,
            "closed_at": case.closed_at.isoformat() if case.closed_at else None,
        },
        "team": [
            {
                "name": m.user.full_name,
                "service_id": m.user.service_id,
                "designation": ROLE_DESIGNATION.get(m.user.role, m.user.role),
                "role_on_case": m.role_on_case,
            }
            for m in members
        ],
        "summary": {
            "entities": len(entity_rows),
            "relationships": len(relationships),
            "observed": len(observed),
            "validated": len(validated),
            "inferred_pending": len(inferred),
            "rejected": len(rejected),
            "events": len(events),
            "evidence_items": len(evidence),
            "incidents": len(incidents),
            "alerts": len(alerts),
            "sos_alerts": len(sos_alerts),
            "patterns": len(detections),
            "investigator_decisions": len(validations),
        },
        "entities": [
            {
                "uid": entity.uid,
                "name": entity.name,
                "type": entity.type,
                "role_in_case": link.role_in_case,
                "aliases": [a.alias for a in entity.aliases],
                "priority_score": round(scores[entity.id].score, 1) if entity.id in scores else None,
                "priority_band": scores[entity.id].band if entity.id in scores else None,
            }
            for entity, link in entity_rows
        ],
        "relationships": {
            "observed": [rel_line(r) for r in observed],
            "validated": [rel_line(r) for r in validated],
            "inferred_pending_validation": [rel_line(r) for r in inferred],
            "rejected": [rel_line(r) for r in rejected],
        },
        "network_findings": {
            "most_connected": [
                {
                    "name": snapshot.nodes[u].name,
                    "type": snapshot.nodes[u].type,
                    "connections": len(snapshot.adjacency.get(u, {})),
                }
                for u in ranked
            ],
            "method": (
                "Degree centrality computed over the entities associated with this "
                "case. Structural prominence only."
            ),
        },
        "priority_analysis": [
            {
                "entity": entity_by_id[s.entity_id].name if s.entity_id in entity_by_id else "?",
                "score": round(s.score, 1),
                "band": s.band,
                "confidence": s.confidence,
                "top_factors": sorted(
                    s.factors, key=lambda f: -f.get("contribution", 0)
                )[:3],
                "computed_at": s.computed_at.isoformat() if s.computed_at else None,
            }
            for s in sorted(scores.values(), key=lambda s: -s.score)[:10]
        ],
        "timeline": [
            {
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                "time_label": e.time_label,
                "type": e.type,
                "title": e.title,
            }
            for e in events
        ],
        "evidence": [
            {
                "evidence_ref": e.evidence_ref,
                "source": e.source,
                "source_type": e.source_type,
                "description": e.description,
                "status": e.status,
                "confidence": e.confidence,
            }
            for e in evidence
        ],
        "women_safety": {
            "incidents": [
                {
                    "incident_ref": i.incident_ref, "type": i.type,
                    "priority": i.priority, "status": i.status,
                    "description": i.description,
                    "occurred_at": i.occurred_at.isoformat() if i.occurred_at else None,
                    "time_label": i.time_label, "location": i.location_text,
                }
                for i in incidents
            ],
            "alerts": [
                {
                    "alert_ref": a.alert_ref, "priority": a.priority,
                    "status": a.status, "message": a.message,
                }
                for a in alerts
            ],
            "sos": [
                {
                    "alert_ref": s.alert_ref, "status": s.status,
                    "subject": s.subject_name,
                    "raised_at": s.raised_at.isoformat() if s.raised_at else None,
                    "location_source": s.location_source,
                    "transitions": [
                        {"to": h.to_status,
                         "at": h.changed_at.isoformat() if h.changed_at else None}
                        for h in s.history
                    ],
                }
                for s in sos_alerts
            ],
            "patterns": [
                {
                    "pattern_ref": p.pattern_ref, "kind": p.kind, "title": p.title,
                    "reason": p.reason, "confidence": round(p.confidence, 3),
                    "status": p.status,
                }
                for p in detections
            ],
        } if (incidents or alerts or sos_alerts or detections) else None,
        "investigator_validation": [
            {
                "decision": v.decision,
                "previous_status": v.previous_status,
                "target_id": v.target_id,
                "rationale": v.rationale,
                "timestamp": v.timestamp.isoformat() if v.timestamp else None,
                "by": db.get(User, v.user_id).full_name if db.get(User, v.user_id) else None,
            }
            for v in validations
        ],
        "notes": [
            {
                "body": n.body,
                "author": n.author.full_name if n.author else None,
                "created_at": n.created_at.isoformat(),
            }
            for n in notes
        ],
        "disclaimer": DISCLAIMER,
    }


@router.get("/case/{case_id}/preview")
def preview(
    case_id: int,
    user: User = Depends(require_permission(Perm.REPORT_GENERATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")
    return compile_report(db, case, user)


@router.post("/case/{case_id}/generate")
def generate(
    case_id: int,
    request: Request,
    user: User = Depends(require_permission(Perm.REPORT_GENERATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Compile and persist a report snapshot."""
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")

    payload = compile_report(db, case, user)
    count = db.scalar(select(func.count()).select_from(Report)) or 0
    report = Report(
        report_ref=f"RPT-{datetime.now(UTC):%Y%m%d}-{count + 1:04d}",
        case_id=case.id,
        generated_by_id=user.id,
        generated_at=datetime.now(UTC),
        title=f"Investigation Report - {case.case_number}",
        payload=payload,
    )
    db.add(report)
    db.flush()
    record_audit(
        db, action="REPORT_GENERATED", user=user, resource_type="report",
        resource_id=report.report_ref, case_id=case.id,
        detail=f"{case.case_number}: {payload['summary']['entities']} entities, "
               f"{payload['summary']['relationships']} relationships",
        ip_address=client_ip(request),
    )
    db.commit()
    return {
        "report_ref": report.report_ref,
        "report_id": report.id,
        "generated_at": report.generated_at.isoformat(),
        "summary": payload["summary"],
    }


@router.get("")
def list_reports(
    case_id: int | None = None,
    user: User = Depends(require_permission(Perm.REPORT_GENERATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Report)
    if case_id:
        stmt = stmt.where(Report.case_id == case_id)
    rows = db.scalars(stmt.order_by(Report.generated_at.desc()).limit(50)).all()
    return {
        "items": [
            {
                "report_ref": r.report_ref,
                "report_id": r.id,
                "title": r.title,
                "case_id": r.case_id,
                "case_number": r.case.case_number if r.case else None,
                "generated_by": r.generated_by.full_name if r.generated_by else None,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "summary": (r.payload or {}).get("summary", {}),
            }
            for r in rows
        ]
    }


@router.get("/{report_ref}/json")
def export_json(
    report_ref: str,
    request: Request,
    user: User = Depends(require_permission(Perm.DATA_EXPORT)),
    db: Session = Depends(get_db),
) -> Response:
    report = db.scalars(select(Report).where(Report.report_ref == report_ref)).first()
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    record_audit(
        db, action="REPORT_EXPORTED", user=user, resource_type="report",
        resource_id=report_ref, case_id=report.case_id, detail="JSON export",
        ip_address=client_ip(request),
    )
    db.commit()
    return Response(
        content=json.dumps(report.payload, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{report_ref}.json"'},
    )


@router.get("/{report_ref}/pdf")
def export_pdf(
    report_ref: str,
    request: Request,
    user: User = Depends(require_permission(Perm.DATA_EXPORT)),
    db: Session = Depends(get_db),
) -> Response:
    """Render the stored report snapshot as a PDF."""
    report = db.scalars(select(Report).where(Report.report_ref == report_ref)).first()
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")

    pdf_bytes = _render_pdf(report.report_ref, report.payload or {})

    record_audit(
        db, action="REPORT_EXPORTED", user=user, resource_type="report",
        resource_id=report_ref, case_id=report.case_id, detail="PDF export",
        ip_address=client_ip(request),
    )
    db.commit()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report_ref}.pdf"'},
    )


def _render_pdf(report_ref: str, data: dict[str, Any]) -> bytes:
    """Render the stored report snapshot as a PDF."""
    from app.api.v1.reports_pdf import render_pdf

    return render_pdf(report_ref, data)
