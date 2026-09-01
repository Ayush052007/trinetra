"""Suspicious-pattern and repeated-encounter detection.

Both detectors connect Women Safety incidents to the criminal-network graph:
they operate over the same entities table, so a pattern found here can be
opened directly as a subgraph.

Wording is a hard constraint, not a style choice. These detectors output
"potential patterns requiring authorised investigator review". They never
identify a stalker, never assert intent, and never assert an offence.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import EvidenceStatus
from app.db.models import Entity, Event, Relationship
from app.db.models_safety import Incident, PatternDetection
from app.services import graph_service

PATTERN_VERSION = "pattern-1.0"

REVIEW_NOTICE = "Requires authorized investigator review."


def _next_ref(db: Session, prefix: str) -> str:
    count = db.scalar(select(PatternDetection.id).order_by(PatternDetection.id.desc())) or 0
    return f"{prefix}-{count + 1:04d}"


# ============================================== suspicious patterns


def detect_suspicious_patterns(
    db: Session, case_id: int | None = None, min_incidents: int = 2
) -> list[dict[str, Any]]:
    """Cross-incident clustering on shared descriptors and entities.

    Groups incidents that share a vehicle description, a device identifier, a
    named entity, or a repeated location/time-window signature. Each group is
    reported with the exact incidents that formed it.
    """
    query = select(Incident)
    if case_id is not None:
        query = query.where(Incident.case_id == case_id)
    incidents = list(db.scalars(query).all())
    if not incidents:
        return []

    entities = {e.id: e for e in db.scalars(select(Entity)).all()}
    results: list[dict[str, Any]] = []

    def build(kind: str, title: str, reason: str, group: list[Incident],
              confidence: float, factors: list[dict], entity_ids: list[int]) -> dict[str, Any]:
        return {
            "kind": kind,
            "title": title,
            "reason": reason,
            "confidence": round(confidence, 3),
            "status": "PENDING_REVIEW",
            "incident_count": len(group),
            "supporting_incidents": [
                {
                    "ref": i.incident_ref, "type": i.type, "priority": i.priority,
                    "occurred_at": i.occurred_at.isoformat() if i.occurred_at else None,
                    "time_label": i.time_label, "location": i.location_text,
                    "description": i.description,
                }
                for i in group
            ],
            # Several incidents in a group commonly share the same subject, so
            # deduplicate rather than listing an entity more than once.
            "supporting_entities": [
                {"uid": entities[e].uid, "name": entities[e].name, "type": entities[e].type}
                for e in dict.fromkeys(entity_ids) if e in entities
            ],
            "factors": factors,
            "algorithm_version": PATTERN_VERSION,
            "notice": REVIEW_NOTICE,
            "disclaimer": (
                "An analytical pattern over recorded incidents. It does not "
                "establish that any offence occurred or identify any individual "
                "as responsible."
            ),
        }

    # 1. Shared vehicle description.
    by_vehicle: dict[str, list[Incident]] = defaultdict(list)
    for incident in incidents:
        vehicle = (incident.descriptors or {}).get("vehicle")
        if vehicle:
            by_vehicle[str(vehicle).replace(" ", "").upper()].append(incident)
    for vehicle, group in by_vehicle.items():
        if len(group) < min_incidents:
            continue
        locations = {i.location_text for i in group if i.location_text}
        results.append(build(
            "similar_vehicle",
            f"Repeated vehicle descriptor across {len(group)} incidents",
            (
                f"The same vehicle descriptor appears in {len(group)} separate incident "
                f"reports across {len(locations)} location(s)."
            ),
            group,
            min(0.88, 0.45 + 0.13 * len(group) + 0.05 * len(locations)),
            [
                {"label": "Shared descriptor", "detail": f"Vehicle {vehicle}"},
                {"label": "Distinct locations", "detail": f"{len(locations)}: " + ", ".join(sorted(locations)[:4])},
                {"label": "Incident count", "detail": str(len(group))},
            ],
            [i.subject_entity_id for i in group if i.subject_entity_id],
        ))

    # 2. Shared device / phone identifier.
    by_device: dict[str, list[Incident]] = defaultdict(list)
    for incident in incidents:
        device = (incident.descriptors or {}).get("device")
        if device:
            by_device[str(device)].append(incident)
    for device, group in by_device.items():
        if len(group) < min_incidents:
            continue
        results.append(build(
            "recurring_device",
            f"Recurring device identifier across {len(group)} incidents",
            (
                f"The identifier {device} recurs across {len(group)} incident reports, "
                f"suggesting a single contact channel rather than unrelated reports."
            ),
            group,
            min(0.85, 0.45 + 0.14 * len(group)),
            [
                {"label": "Shared identifier", "detail": device},
                {"label": "Incident count", "detail": str(len(group))},
            ],
            [i.subject_entity_id for i in group if i.subject_entity_id],
        ))

    # 3. Repeated location concentration.
    by_location: dict[int, list[Incident]] = defaultdict(list)
    for incident in incidents:
        if incident.location_entity_id:
            by_location[incident.location_entity_id].append(incident)
    for location_id, group in by_location.items():
        if len(group) < max(min_incidents + 1, 3):
            continue
        types = {i.type for i in group}
        location = entities.get(location_id)
        results.append(build(
            "location_concentration",
            f"{len(group)} incidents concentrated at {location.name if location else 'one location'}",
            (
                f"{len(group)} incidents spanning {len(types)} incident type(s) are "
                f"recorded at the same location."
            ),
            group,
            min(0.80, 0.35 + 0.11 * len(group)),
            [
                {"label": "Location", "detail": location.name if location else str(location_id)},
                {"label": "Incident types", "detail": ", ".join(sorted(types))},
                {"label": "Incident count", "detail": str(len(group))},
            ],
            [location_id],
        ))

    # 4. Incidents sharing a subject entity that also appears in the network graph.
    by_subject: dict[int, list[Incident]] = defaultdict(list)
    for incident in incidents:
        if incident.subject_entity_id:
            by_subject[incident.subject_entity_id].append(incident)
    for subject_id, group in by_subject.items():
        if len(group) < max(min_incidents + 1, 3):
            continue
        subject = entities.get(subject_id)
        if subject is None:
            continue
        repo = graph_service.get_graph(db)
        neighbours = repo.snapshot().adjacency.get(subject.uid, {})
        results.append(build(
            "common_entity",
            f"{len(group)} incidents share a common entity: {subject.name}",
            (
                f"{len(group)} incidents reference {subject.name}, which is connected "
                f"to {len(neighbours)} other entities in the knowledge graph."
            ),
            group,
            min(0.82, 0.40 + 0.10 * len(group)),
            [
                {"label": "Common entity", "detail": f"{subject.name} ({subject.type})"},
                {"label": "Graph connections", "detail": f"{len(neighbours)} linked entities"},
                {"label": "Incident count", "detail": str(len(group))},
            ],
            [subject_id],
        ))

    results.sort(key=lambda r: -r["confidence"])
    return results


# ========================================== repeated-encounter detection


def _describe_event(
    location_uid: str, when: datetime | None, provenance: Any, entities: dict
) -> dict[str, Any]:
    """Render one co-occurrence event, whichever source it came from."""
    base = {
        "location": entities[location_uid].name if location_uid in entities else location_uid,
        "location_uid": location_uid,
        "occurred_at": when.isoformat() if when else None,
    }
    if isinstance(provenance, Incident):
        return {
            **base,
            "kind": "incident",
            "time_label": provenance.time_label,
            "incident_ref": provenance.incident_ref,
            "incident_type": provenance.type,
            "priority": provenance.priority,
            "description": provenance.description,
            "evidence_status": "OBSERVED",
        }
    return {
        **base,
        "kind": "relationship",
        "time_label": provenance.time_label,
        "relationship_type": provenance.type,
        "relationship_id": provenance.id,
        "source_ref": provenance.source,
        "evidence_status": provenance.evidence_status,
    }


def detect_repeated_encounters(
    db: Session,
    subject_uid: str | None = None,
    case_id: int | None = None,
    min_confidence: float = 0.55,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Co-occurrence analysis across person, vehicle, location, time and device.

    For each (subject, counterpart) pair, counts how often the counterpart is
    recorded at the same locations as the subject, across how many distinct
    days, and whether the pattern is escalating. Reports the actual events
    that produced the finding.
    """
    repo = graph_service.get_graph(db)
    snapshot = repo.snapshot()
    entities = {e.uid: e for e in db.scalars(select(Entity)).all()}

    # Location associations per entity, with the events that recorded them.
    relationships = list(
        db.scalars(
            select(Relationship).where(
                Relationship.evidence_status != EvidenceStatus.REJECTED
            )
        ).all()
    )
    id_to_uid = {e.id: e.uid for e in entities.values()}

    # A co-occurrence event is (location_uid, when, provenance). Two sources
    # feed it, because the evidence for a repeated encounter is split across
    # both in real case data:
    #   1. relationships that place an entity at a location, and
    #   2. incident reports, which carry a subject, a location, a time and
    #      descriptors naming a vehicle or device.
    # Reading only relationships misses the incident-borne half entirely.
    location_events: dict[str, list[tuple[str, datetime | None, Any]]] = defaultdict(list)

    for r in relationships:
        su, tu = id_to_uid.get(r.source_id), id_to_uid.get(r.target_id)
        if not su or not tu:
            continue
        for a, b in ((su, tu), (tu, su)):
            target = entities.get(b)
            if target is not None and target.type == "location":
                location_events[a].append((b, r.occurred_at, r))

    # Index descriptors so an incident naming a vehicle or device registration
    # attributes the sighting to that entity.
    descriptor_index: dict[str, str] = {}
    for entity in entities.values():
        if entity.type in ("vehicle", "phone", "social"):
            key = entity.name.replace(" ", "").replace("-", "").upper()
            descriptor_index[key] = entity.uid

    incident_query = select(Incident).where(Incident.location_entity_id.is_not(None))
    if case_id is not None:
        incident_query = incident_query.where(Incident.case_id == case_id)
    for incident in db.scalars(incident_query).all():
        location_uid = id_to_uid.get(incident.location_entity_id)
        if not location_uid:
            continue
        if incident.subject_entity_id:
            subject_uid = id_to_uid.get(incident.subject_entity_id)
            if subject_uid:
                location_events[subject_uid].append(
                    (location_uid, incident.occurred_at, incident)
                )
        for value in (incident.descriptors or {}).values():
            key = str(value).replace(" ", "").replace("-", "").upper()
            matched = descriptor_index.get(key)
            if matched:
                location_events[matched].append(
                    (location_uid, incident.occurred_at, incident)
                )

    # Scope. Without this the detector sweeps every entity in the background
    # corpus and returns tens of thousands of co-occurrences that no
    # investigator asked about and none of which relate to a case.
    if subject_uid:
        subjects = [subject_uid]
    elif case_id is not None:
        from app.db.models import CaseEntity

        scoped_ids = db.scalars(
            select(CaseEntity.entity_id).where(CaseEntity.case_id == case_id)
        ).all()
        scoped_uids = {
            id_to_uid[i] for i in scoped_ids if i in id_to_uid
        }
        subjects = [uid for uid in location_events if uid in scoped_uids]
    else:
        # No case given: restrict to entities that actually appear in safety
        # incidents. Sweeping the whole background corpus would return
        # thousands of co-occurrences that belong to no investigation and
        # bury the findings that do.
        incident_entity_ids = set(
            db.scalars(select(Incident.subject_entity_id).where(
                Incident.subject_entity_id.is_not(None)
            )).all()
        ) | set(
            db.scalars(select(Incident.location_entity_id).where(
                Incident.location_entity_id.is_not(None)
            )).all()
        )
        safety_uids = {id_to_uid[i] for i in incident_entity_ids if i in id_to_uid}
        # Include anything sharing a location with an incident subject.
        subjects = [uid for uid in location_events if uid in safety_uids]

    findings: list[dict[str, Any]] = []

    for subject in subjects:
        subject_entity = entities.get(subject)
        if subject_entity is None:
            continue
        subject_locations = {loc for loc, _, _ in location_events.get(subject, [])}
        if not subject_locations:
            continue

        for counterpart, records in location_events.items():
            if counterpart == subject:
                continue
            counterpart_entity = entities.get(counterpart)
            if counterpart_entity is None:
                continue
            # A person and the vehicle/person recorded alongside them.
            if counterpart_entity.type not in ("person", "vehicle", "phone", "social"):
                continue
            # Skip anything with a directly recorded relationship - that is a
            # known association, not a repeated-encounter finding.
            if counterpart in snapshot.adjacency.get(subject, {}):
                continue

            overlap = []
            seen_slots: set[tuple[str, str]] = set()
            for loc, when, provenance in records:
                if loc not in subject_locations:
                    continue
                # One sighting can be recorded both as a relationship and as an
                # incident; counting it twice would inflate the pattern.
                slot = (loc, when.date().isoformat() if when else "undated")
                if slot in seen_slots:
                    continue
                seen_slots.add(slot)
                overlap.append((loc, when, provenance))
            if len(overlap) < 2:
                continue

            distinct_locations = {loc for loc, _, _ in overlap}
            distinct_days = {
                when.date() for _, when, _ in overlap if when is not None
            }
            if len(distinct_locations) < 2 and len(distinct_days) < 2:
                continue

            dates = sorted(w for _, w, _ in overlap if w is not None)
            escalating = False
            if len(dates) >= 3:
                first_half = (dates[len(dates) // 2] - dates[0]).days or 1
                second_half = (dates[-1] - dates[len(dates) // 2]).days or 1
                escalating = second_half < first_half

            confidence = min(
                0.90,
                0.28
                + 0.14 * len(distinct_locations)
                + 0.09 * len(distinct_days)
                + (0.08 if escalating else 0.0),
            )

            supporting_events = [
                _describe_event(loc, when, provenance, entities)
                for loc, when, provenance in sorted(
                    overlap, key=lambda x: (x[1] or datetime.min.replace(tzinfo=UTC))
                )
            ]

            findings.append({
                "kind": "repeated_encounter",
                "title": (
                    f"Potential repeated-encounter pattern - {counterpart_entity.name} "
                    f"and {subject_entity.name}"
                ),
                "subject": {
                    "uid": subject_entity.uid, "name": subject_entity.name,
                    "type": subject_entity.type,
                },
                "counterpart": {
                    "uid": counterpart_entity.uid, "name": counterpart_entity.name,
                    "type": counterpart_entity.type,
                },
                "confidence": round(confidence, 3),
                "status": "PENDING_REVIEW",
                "reason": (
                    f"{counterpart_entity.name} is recorded at "
                    f"{len(distinct_locations)} location(s) also associated with "
                    f"{subject_entity.name}, across {len(distinct_days) or 'an unknown number of'} "
                    f"distinct day(s)"
                    + (", with decreasing intervals between occurrences" if escalating else "")
                    + "."
                ),
                "factors": [
                    {
                        "label": "Shared locations",
                        "value": len(distinct_locations),
                        "detail": ", ".join(
                            entities[loc].name for loc in sorted(distinct_locations)
                            if loc in entities
                        ),
                    },
                    {
                        "label": "Distinct days",
                        "value": len(distinct_days),
                        "detail": ", ".join(sorted(str(d) for d in distinct_days)[:5]) or "not dated",
                    },
                    {
                        "label": "Escalation trend",
                        "value": escalating,
                        "detail": (
                            "Intervals between recorded occurrences are shortening"
                            if escalating
                            else "No escalation trend detectable from the available dates"
                        ),
                    },
                    {
                        "label": "Direct relationship on record",
                        "value": False,
                        "detail": "No directly recorded association between the two entities",
                    },
                ],
                "supporting_events": supporting_events,
                "algorithm_version": PATTERN_VERSION,
                "notice": REVIEW_NOTICE,
                "disclaimer": (
                    "This is a co-occurrence pattern in recorded data. It does not "
                    "identify anyone as a stalker, establish intent, or assert that "
                    "an offence occurred. Authorised investigator review is required."
                ),
            })

    findings = [f for f in findings if f["confidence"] >= min_confidence]
    findings.sort(key=lambda f: -f["confidence"])
    return findings[:limit]


# ====================================================== persistence


def persist_patterns(db: Session, case_id: int | None = None) -> int:
    """Recompute detections and store them for review tracking."""
    existing = {
        (row.kind, row.title): row
        for row in db.scalars(select(PatternDetection)).all()
    }
    now = datetime.now(UTC)
    stored = 0

    payloads = detect_suspicious_patterns(db, case_id) + detect_repeated_encounters(
        db, case_id=case_id
    )
    for index, payload in enumerate(payloads, start=1):
        key = (payload["kind"], payload["title"])
        if key in existing:
            row = existing[key]
            row.confidence = payload["confidence"]
            row.computed_at = now
            continue
        subject_uid = (payload.get("subject") or {}).get("uid")
        counterpart_uid = (payload.get("counterpart") or {}).get("uid")
        subject = (
            db.scalars(select(Entity).where(Entity.uid == subject_uid)).first()
            if subject_uid else None
        )
        counterpart = (
            db.scalars(select(Entity).where(Entity.uid == counterpart_uid)).first()
            if counterpart_uid else None
        )
        db.add(
            PatternDetection(
                pattern_ref=f"PAT-{now:%Y%m%d}-{index:04d}",
                kind=payload["kind"],
                title=payload["title"][:250],
                reason=payload["reason"],
                confidence=payload["confidence"],
                status="PENDING_REVIEW",
                case_id=case_id,
                subject_entity_id=subject.id if subject else None,
                counterpart_entity_id=counterpart.id if counterpart else None,
                supporting_incidents=[
                    i["ref"] for i in payload.get("supporting_incidents", [])
                ],
                supporting_events=payload.get("supporting_events", []),
                supporting_entities=[
                    e["uid"] for e in payload.get("supporting_entities", [])
                ],
                factors=payload.get("factors", []),
                algorithm_version=PATTERN_VERSION,
                computed_at=now,
            )
        )
        stored += 1
    db.flush()
    return stored
