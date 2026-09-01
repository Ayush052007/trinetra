"""Women Safety Intelligence endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import Perm
from app.db.base import AlertStatus, Priority, SosStatus
from app.db.models import Case, Entity, User
from app.db.models_safety import (
    EmergencyContact,
    EmergencyService,
    Incident,
    IncidentType,
    PatternDetection,
    RouteQuery,
    SafetyAlert,
    SafetyZone,
    SosAlert,
    SosStatusHistory,
    Waypoint,
)
from app.db.session import get_db
from app.services import patterns as pattern_service
from app.services import safety as safety_service
from app.services.mutations import record_audit
from app.services.realtime import broadcast

router = APIRouter(prefix="/safety", tags=["women-safety"], dependencies=[Depends(api_rate_limiter)])

# Forward-only workflow. An alert cannot silently regress to an earlier state.
SOS_TRANSITIONS = {
    SosStatus.RECEIVED: {SosStatus.ASSIGNED},
    SosStatus.ASSIGNED: {SosStatus.RESPONDING, SosStatus.RECEIVED},
    SosStatus.RESPONDING: {SosStatus.RESOLVED},
    SosStatus.RESOLVED: set(),
}

ALERT_TRANSITIONS = {
    AlertStatus.NEW: {AlertStatus.ACKNOWLEDGED, AlertStatus.ASSIGNED},
    AlertStatus.ACKNOWLEDGED: {AlertStatus.ASSIGNED, AlertStatus.RESOLVED},
    AlertStatus.ASSIGNED: {AlertStatus.RESPONDING, AlertStatus.RESOLVED},
    AlertStatus.RESPONDING: {AlertStatus.RESOLVED},
    AlertStatus.RESOLVED: set(),
}


class SosCreate(BaseModel):
    subject_name: str = Field("Unnamed subject", max_length=120)
    subject_entity_uid: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_text: str | None = Field(None, max_length=200)
    case_id: int | None = None
    note: str | None = Field(None, max_length=1000)


class SosStatusUpdate(BaseModel):
    status: str = Field(pattern="^(RECEIVED|ASSIGNED|RESPONDING|RESOLVED)$")
    unit_ref: str | None = None
    note: str | None = Field(None, max_length=1000)


class AlertStatusUpdate(BaseModel):
    status: str = Field(pattern="^(NEW|ACKNOWLEDGED|ASSIGNED|RESPONDING|RESOLVED)$")
    note: str | None = Field(None, max_length=1000)


class IncidentCreate(BaseModel):
    type: str
    description: str = Field(min_length=3, max_length=2000)
    priority: str = Field("MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    location_text: str | None = Field(None, max_length=200)
    case_id: int | None = None
    occurred_at: str | None = None
    vehicle_descriptor: str | None = Field(None, max_length=64)
    device_descriptor: str | None = Field(None, max_length=64)


# ============================================================== dashboard


@router.get("/overview")
def overview(
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    if str(root / "database") not in sys.path:
        sys.path.insert(0, str(root / "database"))
    import seed_data as SD

    def count(model, *where) -> int:
        stmt = select(func.count()).select_from(model)
        for clause in where:
            stmt = stmt.where(clause)
        return db.scalar(stmt) or 0

    sos_rows = db.scalars(
        select(SosAlert).order_by(SosAlert.raised_at.desc()).limit(10)
    ).all()

    return {
        "counters": {
            "incidents_total": count(Incident),
            "incidents_critical": count(Incident, Incident.priority == "CRITICAL"),
            "incidents_open": count(Incident, Incident.status.in_(["open", "investigating", "escalated"])),
            "sos_open": count(SosAlert, SosAlert.status != SosStatus.RESOLVED),
            "alerts_open": count(SafetyAlert, SafetyAlert.status != AlertStatus.RESOLVED),
            "patterns_pending": count(PatternDetection, PatternDetection.status == "PENDING_REVIEW"),
            "zones": count(SafetyZone),
            "services": count(EmergencyService),
        },
        "incidents_by_type": [
            {"key": k, "label": IncidentType.LABELS.get(k, k), "count": n}
            for k, n in db.execute(
                select(Incident.type, func.count()).group_by(Incident.type)
                .order_by(func.count().desc())
            ).all()
        ],
        "incidents_by_hour": [
            {"hour": h, "count": n}
            for h, n in db.execute(
                select(Incident.hour_of_day, func.count())
                .where(Incident.hour_of_day.is_not(None))
                .group_by(Incident.hour_of_day).order_by(Incident.hour_of_day)
            ).all()
        ],
        "recent_sos": [_sos_payload(db, s) for s in sos_rows],
        "context_statistics": SD.DELHI_CONTEXT_STATS,
        "integration_notice": {
            "device_gps": settings.ENABLE_DEVICE_GPS,
            "emergency_dispatch": settings.ENABLE_EMERGENCY_DISPATCH,
            "sms_gateway": settings.ENABLE_SMS_GATEWAY,
            "message": (
                "Live device GPS, emergency dispatch and SMS notification are not "
                "connected in this deployment. SOS alerts reach the in-platform "
                "operations console only - no emergency call is placed and no "
                "external service is contacted."
            ),
        },
    }


# ==================================================================== SOS


def _sos_payload(db: Session, alert: SosAlert) -> dict[str, Any]:
    contacts = []
    if alert.subject_entity_id:
        contacts = [
            {"name": c.name, "relation": c.relation, "phone": c.phone,
             "priority_order": c.priority_order}
            for c in db.scalars(
                select(EmergencyContact)
                .where(EmergencyContact.owner_entity_id == alert.subject_entity_id)
                .order_by(EmergencyContact.priority_order)
            ).all()
        ]
    return {
        "alert_ref": alert.alert_ref,
        "id": alert.id,
        "status": alert.status,
        "priority": alert.priority,
        "subject_name": alert.subject_name,
        "subject_entity_uid": (
            db.get(Entity, alert.subject_entity_id).uid if alert.subject_entity_id else None
        ),
        "raised_at": alert.raised_at.isoformat() if alert.raised_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "location": {
            "lat": alert.latitude, "lng": alert.longitude,
            "text": alert.location_text, "source": alert.location_source,
        },
        "location_notice": (
            "Live device GPS is not connected in this deployment. This position is "
            "simulated." if alert.location_source == "SIMULATED" else None
        ),
        "assigned_unit": (
            {"name": alert.assigned_unit.name, "type": alert.assigned_unit.type,
             "contact": alert.assigned_unit.contact}
            if alert.assigned_unit else None
        ),
        "assigned_officer": alert.assigned_officer.full_name if alert.assigned_officer else None,
        "contacts": contacts,
        "contacts_notified": alert.contacts_notified or [],
        "notes": alert.notes,
        "workflow": [s.value for s in SosStatus],
        "allowed_transitions": sorted(SOS_TRANSITIONS.get(alert.status, set())),
        "history": [
            {
                "from": h.from_status, "to": h.to_status,
                "at": h.changed_at.isoformat() if h.changed_at else None,
                "by": h.changed_by.full_name if h.changed_by else "system",
                "note": h.note,
            }
            for h in alert.history
        ],
    }


@router.get("/sos")
def list_sos(
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(SosAlert)
    if status_filter and status_filter.upper() != "ALL":
        stmt = stmt.where(SosAlert.status == status_filter.upper())
    rows = db.scalars(stmt.order_by(SosAlert.raised_at.desc())).all()
    return {
        "items": [_sos_payload(db, s) for s in rows],
        "counts": dict(
            db.execute(select(SosAlert.status, func.count()).group_by(SosAlert.status)).all()
        ),
        "workflow": [s.value for s in SosStatus],
    }


@router.post("/sos", status_code=status.HTTP_201_CREATED)
def raise_sos(
    payload: SosCreate,
    request: Request,
    user: User = Depends(require_permission(Perm.SOS_RAISE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Raise a one-tap SOS alert.

    This notifies the in-platform operations console. It does not place an
    emergency call and does not contact any external service - see
    docs/INTEGRATIONS.md.
    """
    now = datetime.now(UTC)
    count = db.scalar(select(func.count()).select_from(SosAlert)) or 0

    subject = None
    if payload.subject_entity_uid:
        subject = db.scalars(
            select(Entity).where(Entity.uid == payload.subject_entity_uid)
        ).first()

    zones = db.scalars(select(SafetyZone)).all()
    from trinetra_graph.algorithms import haversine_km

    nearest_zone = min(
        zones,
        key=lambda z: haversine_km(z.center_lat, z.center_lng, payload.latitude, payload.longitude),
        default=None,
    )

    contacts = []
    if subject:
        contacts = [
            c.name for c in db.scalars(
                select(EmergencyContact)
                .where(EmergencyContact.owner_entity_id == subject.id)
                .order_by(EmergencyContact.priority_order)
            ).all()
        ]

    alert = SosAlert(
        alert_ref=f"SOS-{now:%Y%m%d}-{count + 1:04d}",
        status=SosStatus.RECEIVED,
        priority=Priority.CRITICAL,
        raised_by_id=user.id,
        subject_entity_id=subject.id if subject else None,
        subject_name=subject.name if subject else payload.subject_name,
        raised_at=now,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_text=payload.location_text or "Reported position",
        # Honest labelling: without a connected GPS source this is simulated.
        location_source="DEVICE" if settings.ENABLE_DEVICE_GPS else "SIMULATED",
        zone_id=nearest_zone.id if nearest_zone else None,
        case_id=payload.case_id,
        notes=payload.note,
        contacts_notified=contacts,
    )
    db.add(alert)
    db.flush()
    db.add(
        SosStatusHistory(
            alert_id=alert.id, from_status=None, to_status=SosStatus.RECEIVED,
            changed_by_id=user.id, changed_at=now,
            note="Alert received by the operations console.",
        )
    )

    linked_alert = SafetyAlert(
        alert_ref=f"A-SOS-{alert.id:04d}",
        module="Women Safety",
        priority=Priority.CRITICAL,
        status=AlertStatus.NEW,
        message=f"SOS raised by {alert.subject_name}",
        detail=payload.note or "One-tap SOS alert awaiting assignment.",
        raised_at=now,
        case_id=payload.case_id,
        sos_alert_id=alert.id,
        zone_id=nearest_zone.id if nearest_zone else None,
        supporting={"sos_ref": alert.alert_ref},
    )
    db.add(linked_alert)

    record_audit(
        db, action="SOS_RAISED", user=user, resource_type="sos_alert",
        resource_id=alert.alert_ref, case_id=payload.case_id,
        detail=f"{alert.subject_name} at {payload.latitude:.4f},{payload.longitude:.4f}",
        ip_address=client_ip(request),
    )
    db.commit()

    payload_out = _sos_payload(db, alert)
    broadcast({"channel": "sos", "event": "created", "data": payload_out})
    return payload_out


@router.get("/sos/{alert_ref}")
def sos_detail(
    alert_ref: str,
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    alert = db.scalars(select(SosAlert).where(SosAlert.alert_ref == alert_ref)).first()
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SOS alert not found.")
    return _sos_payload(db, alert)


@router.patch("/sos/{alert_ref}/status")
def update_sos_status(
    alert_ref: str,
    payload: SosStatusUpdate,
    request: Request,
    user: User = Depends(require_permission(Perm.SAFETY_DISPATCH)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Advance an SOS alert through RECEIVED -> ASSIGNED -> RESPONDING -> RESOLVED."""
    alert = db.scalars(select(SosAlert).where(SosAlert.alert_ref == alert_ref)).first()
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SOS alert not found.")

    target = payload.status.upper()
    allowed = SOS_TRANSITIONS.get(alert.status, set())
    if target not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "message": f"Cannot move an alert from {alert.status} to {target}.",
                "allowed": sorted(allowed),
            },
        )

    previous = alert.status
    now = datetime.now(UTC)
    alert.status = target

    if payload.unit_ref:
        unit = db.scalars(
            select(EmergencyService).where(EmergencyService.service_ref == payload.unit_ref)
        ).first()
        if unit is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Response unit not found.")
        alert.assigned_unit_id = unit.id
    if target == SosStatus.ASSIGNED:
        alert.assigned_officer_id = user.id
    if target == SosStatus.RESOLVED:
        alert.resolved_at = now

    db.add(
        SosStatusHistory(
            alert_id=alert.id, from_status=previous, to_status=target,
            changed_by_id=user.id, changed_at=now, note=payload.note,
        )
    )

    linked = db.scalars(
        select(SafetyAlert).where(SafetyAlert.sos_alert_id == alert.id)
    ).first()
    if linked:
        linked.status = {
            SosStatus.ASSIGNED: AlertStatus.ASSIGNED,
            SosStatus.RESPONDING: AlertStatus.RESPONDING,
            SosStatus.RESOLVED: AlertStatus.RESOLVED,
        }.get(target, linked.status)
        if target == SosStatus.RESOLVED:
            linked.resolved_at = now

    record_audit(
        db, action="SOS_STATUS_CHANGED", user=user, resource_type="sos_alert",
        resource_id=alert.alert_ref, case_id=alert.case_id,
        detail=f"{previous} -> {target}" + (f" | {payload.note}" if payload.note else ""),
        ip_address=client_ip(request),
    )
    db.commit()

    result = _sos_payload(db, alert)
    broadcast({"channel": "sos", "event": "status_changed",
               "data": {"alert_ref": alert.alert_ref, "from": previous, "to": target,
                        "alert": result}})
    return result


# ================================================================ heatmap


@router.get("/heatmap")
def heatmap(
    types: str | None = Query(None, description="Comma-separated incident types"),
    severities: str | None = None,
    hour_from: int | None = Query(None, ge=0, le=23),
    hour_to: int | None = Query(None, ge=0, le=23),
    days: int | None = Query(None, ge=1, le=3650),
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return safety_service.build_heatmap(
        db,
        incident_types=[t.strip() for t in types.split(",") if t.strip()] if types else None,
        severities=[s.strip().upper() for s in severities.split(",") if s.strip()] if severities else None,
        hour_from=hour_from,
        hour_to=hour_to,
        days=days,
    )


# ================================================================= routes


@router.get("/waypoints")
def waypoints(
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = db.scalars(select(Waypoint).order_by(Waypoint.is_endpoint.desc(), Waypoint.name)).all()
    return {
        "items": [
            {
                "ref": w.waypoint_ref, "name": w.name,
                "lat": w.latitude, "lng": w.longitude,
                "is_endpoint": w.is_endpoint,
            }
            for w in rows
        ]
    }


@router.post("/routes")
def routes(
    request: Request,
    from_ref: str = Query(..., alias="from"),
    to_ref: str = Query(..., alias="to"),
    depart_hour: int = Query(12, ge=0, le=23),
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    result = safety_service.compute_routes(db, from_ref, to_ref, depart_hour)
    if result.get("error") == "unknown_waypoint":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or both locations are unknown.")
    if result.get("error") == "same_waypoint":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Start and destination must differ.")
    if result.get("error") == "no_route":
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No route exists between these locations."
        )

    from_wp = db.scalars(select(Waypoint).where(Waypoint.waypoint_ref == from_ref)).first()
    to_wp = db.scalars(select(Waypoint).where(Waypoint.waypoint_ref == to_ref)).first()
    db.add(
        RouteQuery(
            requested_by_id=user.id,
            requested_at=datetime.now(UTC),
            from_waypoint_id=from_wp.id,
            to_waypoint_id=to_wp.id,
            depart_hour=depart_hour,
            routes=result["routes"],
        )
    )
    record_audit(
        db, action="SAFE_ROUTE_COMPUTED", user=user, resource_type="route",
        detail=f"{from_wp.name} -> {to_wp.name} at {depart_hour:02d}:00",
        ip_address=client_ip(request),
    )
    db.commit()
    return result


@router.get("/services/nearby")
def services_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, gt=0, le=50),
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    services = safety_service.nearby_services(db, lat, lng, radius_km)
    return {
        "items": services,
        "count": len(services),
        "origin": {"lat": lat, "lng": lng},
        "notice": (
            "Emergency service locations come from configured deployment data. "
            "Live directory and availability APIs are not connected."
        ),
    }


# =============================================================== incidents


@router.get("/incidents")
def list_incidents(
    case_id: int | None = None,
    type_filter: str | None = Query(None, alias="type"),
    priority_filter: str | None = Query(None, alias="priority"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Incident)
    if case_id:
        stmt = stmt.where(Incident.case_id == case_id)
    if type_filter:
        stmt = stmt.where(Incident.type == type_filter)
    if priority_filter:
        stmt = stmt.where(Incident.priority == priority_filter.upper())

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Incident.occurred_at.desc().nullslast()).offset(offset).limit(limit)
    ).all()

    return {
        "total": total,
        "items": [
            {
                "incident_ref": i.incident_ref,
                "type": i.type,
                "type_label": IncidentType.LABELS.get(i.type, i.type),
                "priority": i.priority,
                "status": i.status,
                "description": i.description,
                "occurred_at": i.occurred_at.isoformat() if i.occurred_at else None,
                "time_label": i.time_label,
                "hour_of_day": i.hour_of_day,
                "location_text": i.location_text,
                "coordinates": (
                    {"lat": i.latitude, "lng": i.longitude}
                    if i.latitude is not None else None
                ),
                "subject_uid": (
                    db.get(Entity, i.subject_entity_id).uid if i.subject_entity_id else None
                ),
                "case_id": i.case_id,
                "descriptors": i.descriptors or {},
                "classification": i.data_classification,
            }
            for i in rows
        ],
        "types": [{"key": t, "label": IncidentType.LABELS[t]} for t in IncidentType.ALL],
    }


@router.post("/incidents", status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    user: User = Depends(require_permission(Perm.SAFETY_INCIDENT_CREATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.type not in IncidentType.ALL:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"message": "Unknown incident type.", "allowed": IncidentType.ALL},
        )
    now = datetime.now(UTC)
    count = db.scalar(select(func.count()).select_from(Incident)) or 0

    occurred = now
    if payload.occurred_at:
        try:
            occurred = datetime.fromisoformat(payload.occurred_at)
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=UTC)
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "occurred_at must be an ISO 8601 datetime."
            ) from None

    zone = None
    if payload.latitude is not None and payload.longitude is not None:
        from trinetra_graph.algorithms import haversine_km

        zone = min(
            db.scalars(select(SafetyZone)).all(),
            key=lambda z: haversine_km(z.center_lat, z.center_lng, payload.latitude, payload.longitude),
            default=None,
        )

    descriptors: dict[str, Any] = {}
    if payload.vehicle_descriptor:
        descriptors["vehicle"] = payload.vehicle_descriptor
    if payload.device_descriptor:
        descriptors["device"] = payload.device_descriptor

    incident = Incident(
        incident_ref=f"WSI-{now:%Y%m%d}-{count + 1:04d}",
        type=payload.type,
        description=payload.description,
        priority=payload.priority,
        status="open",
        occurred_at=occurred,
        hour_of_day=occurred.hour,
        case_id=payload.case_id,
        zone_id=zone.id if zone else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_text=payload.location_text,
        descriptors=descriptors,
        reported_by_id=user.id,
    )
    db.add(incident)
    db.flush()

    record_audit(
        db, action="INCIDENT_CREATED", user=user, resource_type="incident",
        resource_id=incident.incident_ref, case_id=payload.case_id,
        detail=f"{payload.type} ({payload.priority})", ip_address=client_ip(request),
    )
    db.commit()
    broadcast({
        "channel": "incidents", "event": "created",
        "data": {"incident_ref": incident.incident_ref, "type": incident.type,
                 "priority": incident.priority},
    })
    return {
        "incident_ref": incident.incident_ref,
        "message": "Incident recorded. Heatmap density and pattern detection now include it.",
    }


# ================================================================ patterns


@router.get("/patterns")
def get_patterns(
    case_id: int | None = None,
    refresh: bool = False,
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Suspicious clusters and repeated-encounter findings."""
    if refresh:
        pattern_service.persist_patterns(db, case_id)
        db.commit()

    stored = db.scalars(
        select(PatternDetection)
        .where(PatternDetection.case_id == case_id if case_id else True)
        .order_by(PatternDetection.confidence.desc())
    ).all()

    live_suspicious = pattern_service.detect_suspicious_patterns(db, case_id)
    live_encounters = pattern_service.detect_repeated_encounters(db, case_id=case_id)

    return {
        "stored": [
            {
                "id": p.id,
                "pattern_ref": p.pattern_ref,
                "kind": p.kind,
                "title": p.title,
                "reason": p.reason,
                "confidence": round(p.confidence, 3),
                "status": p.status,
                "supporting_incidents": p.supporting_incidents,
                "supporting_events": p.supporting_events,
                "supporting_entities": p.supporting_entities,
                "factors": p.factors,
                "subject_uid": (
                    db.get(Entity, p.subject_entity_id).uid if p.subject_entity_id else None
                ),
                "counterpart_uid": (
                    db.get(Entity, p.counterpart_entity_id).uid
                    if p.counterpart_entity_id else None
                ),
                "computed_at": p.computed_at.isoformat() if p.computed_at else None,
                "notice": pattern_service.REVIEW_NOTICE,
            }
            for p in stored
        ],
        "suspicious_patterns": live_suspicious,
        "repeated_encounters": live_encounters,
        "counts": {
            "stored": len(stored),
            "suspicious": len(live_suspicious),
            "repeated_encounters": len(live_encounters),
            "pending_review": sum(1 for p in stored if p.status == "PENDING_REVIEW"),
        },
        "disclaimer": (
            "These are analytical patterns over recorded data. They do not identify "
            "any person as an offender, do not establish intent, and require "
            "authorised investigator review."
        ),
    }


@router.post("/patterns/{pattern_id}/review")
def review_pattern(
    pattern_id: int,
    payload: AlertStatusUpdate,
    request: Request,
    user: User = Depends(require_permission(Perm.SAFETY_READ, Perm.RELATIONSHIP_VALIDATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    pattern = db.get(PatternDetection, pattern_id)
    if pattern is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pattern not found.")
    decision = payload.status.upper()
    if decision not in ("ACKNOWLEDGED", "RESOLVED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A pattern review decision must be ACKNOWLEDGED or RESOLVED.",
        )
    pattern.status = "REVIEWED" if decision == "ACKNOWLEDGED" else "CLOSED"
    pattern.reviewed_by_id = user.id
    pattern.reviewed_at = datetime.now(UTC)
    record_audit(
        db, action="PATTERN_REVIEWED", user=user, resource_type="pattern",
        resource_id=pattern.pattern_ref, case_id=pattern.case_id,
        detail=f"{pattern.status}" + (f" | {payload.note}" if payload.note else ""),
        ip_address=client_ip(request),
    )
    db.commit()
    return {"pattern_ref": pattern.pattern_ref, "status": pattern.status}


# ================================================================== alerts


@router.get("/alerts")
def list_alerts(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(SafetyAlert)
    if status_filter and status_filter.upper() != "ALL":
        stmt = stmt.where(SafetyAlert.status == status_filter.upper())
    rows = db.scalars(stmt.order_by(SafetyAlert.raised_at.desc()).limit(limit)).all()

    priority_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    items = sorted(
        [
            {
                "id": a.id,
                "alert_ref": a.alert_ref,
                "module": a.module,
                "priority": a.priority,
                "status": a.status,
                "message": a.message,
                "detail": a.detail,
                "raised_at": a.raised_at.isoformat() if a.raised_at else None,
                "time_label": a.time_label,
                "case_id": a.case_id,
                "sos_alert_id": a.sos_alert_id,
                "assigned_to": a.assigned_to.full_name if a.assigned_to else None,
                "supporting": a.supporting or {},
                "allowed_transitions": sorted(ALERT_TRANSITIONS.get(a.status, set())),
            }
            for a in rows
        ],
        key=lambda a: (priority_rank.get(a["priority"], 9), a["raised_at"] or ""),
    )
    return {
        "items": items,
        "counts": dict(
            db.execute(
                select(SafetyAlert.status, func.count()).group_by(SafetyAlert.status)
            ).all()
        ),
        "workflow": [s.value for s in AlertStatus],
    }


@router.patch("/alerts/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    request: Request,
    user: User = Depends(require_permission(Perm.SAFETY_DISPATCH)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    alert = db.get(SafetyAlert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    target = payload.status.upper()
    allowed = ALERT_TRANSITIONS.get(alert.status, set())
    if target not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "message": f"Cannot move an alert from {alert.status} to {target}.",
                "allowed": sorted(allowed),
            },
        )
    previous = alert.status
    now = datetime.now(UTC)
    alert.status = target
    if target == AlertStatus.ACKNOWLEDGED:
        alert.acknowledged_at = now
    if target in (AlertStatus.ASSIGNED, AlertStatus.RESPONDING):
        alert.assigned_to_id = user.id
    if target == AlertStatus.RESOLVED:
        alert.resolved_at = now

    record_audit(
        db, action="ALERT_STATUS_CHANGED", user=user, resource_type="safety_alert",
        resource_id=alert.alert_ref, case_id=alert.case_id,
        detail=f"{previous} -> {target}", ip_address=client_ip(request),
    )
    db.commit()
    broadcast({
        "channel": "alerts", "event": "status_changed",
        "data": {"alert_ref": alert.alert_ref, "from": previous, "to": target},
    })
    return {"alert_ref": alert.alert_ref, "status": alert.status, "previous": previous}


@router.get("/zones")
def zones(
    user: User = Depends(require_permission(Perm.SAFETY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = db.scalars(select(SafetyZone)).all()
    return {
        "items": [
            {
                "zone_ref": z.zone_ref, "name": z.name, "description": z.description,
                "center": {"lat": z.center_lat, "lng": z.center_lng},
                "radius_km": z.radius_km, "classification": z.data_classification,
            }
            for z in rows
        ]
    }
