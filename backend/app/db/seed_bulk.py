"""Corpus loading, derived analytics and the seed_all orchestrator."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
for _p in (PROJECT_ROOT / "database", PROJECT_ROOT / "ai", PROJECT_ROOT / "graph"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from generator import CorpusGenerator  # noqa: E402

from app.db.base import Base, DataClassification, EvidenceStatus, Priority  # noqa: E402
from app.db.models import (  # noqa: E402
    AuditLog,
    Case,
    CaseEntity,
    CaseMember,
    Entity,
    IngestionJob,
    Notification,
    Record,
    User,
)
from app.db.models_safety import Incident, SafetyZone  # noqa: E402
from app.db.seed import (  # noqa: E402
    CORE_CASE_NUMBER,
    WS_CASE_NUMBER,
    EntityWriter,
    seed_core_case,
    seed_safety,
    seed_users,
    seed_ws_case,
    write_credentials_file,
)
from app.db.session import SessionLocal, create_all, engine  # noqa: E402
from app.services import discovery, graph_service, patterns, priority  # noqa: E402


def _content_hash(payload: dict) -> str:
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def seed_corpus(db: Session, writer: EntityWriter, analyst: User) -> dict[str, int]:
    """Load the generated background population."""
    corpus = CorpusGenerator().generate()

    # Bulk load: batch flushes. Restored before returning so any later
    # id-dependent seeding still behaves exactly as before.
    previous_flush_every = writer.flush_every
    writer.flush_every = 500

    # Commit periodically. The whole corpus in one transaction is fine locally
    # but fragile over a remote link, where a single dropped connection would
    # discard tens of thousands of rows.
    for index, entity in enumerate(corpus.entities, 1):
        writer.entity(
            entity.uid,
            entity.type,
            entity.name,
            aliases=entity.aliases,
            attributes={**entity.attributes, "community": entity.community},
            source="Generated background corpus",
            latitude=entity.latitude,
            longitude=entity.longitude,
            classification=DataClassification.SYNTHETIC,
        )
        if index % 500 == 0:
            db.commit()
    db.commit()

    job = IngestionJob(
        filename="synthetic_background_corpus.generated",
        source_type="Mixed",
        uploaded_by_id=analyst.id,
        started_at=datetime.now(UTC) - timedelta(minutes=6),
        finished_at=datetime.now(UTC) - timedelta(minutes=4),
        status="COMPLETE",
        stage="complete",
        records_received=len(corpus.records),
        records_processed=len(corpus.records),
        duplicates=0,
        entities_extracted=len(corpus.entities),
        relationships_created=len(corpus.relationships),
        stage_log=[
            {"stage": "validate", "status": "complete"},
            {"stage": "parse", "status": "complete"},
            {"stage": "normalise", "status": "complete"},
            {"stage": "deduplicate", "status": "complete"},
            {"stage": "extract", "status": "complete"},
            {"stage": "resolve", "status": "complete"},
            {"stage": "relate", "status": "complete"},
            {"stage": "graph", "status": "complete"},
        ],
    )
    db.add(job)
    db.flush()

    for index, relationship in enumerate(corpus.relationships, 1):
        writer.relationship(
            relationship.source_uid,
            relationship.target_uid,
            relationship.type,
            source_ref=relationship.source_ref,
            occurred_at=relationship.occurred_at,
            confidence=relationship.confidence,
            attributes=relationship.attributes,
        )
        if index % 500 == 0:
            db.commit()
    db.commit()

    seen: set[str] = set()
    duplicates = 0
    for record in corpus.records:
        digest = _content_hash(record.payload)
        is_duplicate = digest in seen
        if is_duplicate:
            duplicates += 1
        seen.add(digest)
        db.add(
            Record(
                job_id=job.id,
                source_type=record.source_type,
                source_ref=record.source_ref,
                occurred_at=record.occurred_at,
                payload=record.payload,
                content_hash=digest,
                is_duplicate=is_duplicate,
                created_at=record.occurred_at,
            )
        )
    job.duplicates = duplicates

    zone_rows = list(db.scalars(select(SafetyZone)).all())
    for item in corpus.incidents:
        location = writer.by_uid.get(item["location_uid"])
        # Attach to the nearest configured zone so background incidents feed
        # the same density computation as case incidents.
        from trinetra_graph.algorithms import haversine_km

        nearest = min(
            zone_rows,
            key=lambda z: haversine_km(z.center_lat, z.center_lng, item["latitude"], item["longitude"]),
            default=None,
        )
        db.add(
            Incident(
                incident_ref=item["incident_ref"],
                type=item["type"],
                description=item["description"],
                priority=item["priority"],
                status=item["status"],
                occurred_at=item["occurred_at"],
                hour_of_day=item["hour_of_day"],
                location_entity_id=location.id if location else None,
                zone_id=nearest.id if nearest else None,
                latitude=item["latitude"],
                longitude=item["longitude"],
                location_text=item["location_text"],
            )
        )

    db.flush()
    writer.flush_every = previous_flush_every
    return {
        "entities": len(corpus.entities),
        "relationships": len(corpus.relationships),
        "records": len(corpus.records),
        "incidents": len(corpus.incidents),
        "duplicates": duplicates,
    }


EVENT_TYPE_FOR_RELATIONSHIP = {
    "CALLED": "communication",
    "MET": "meeting",
    "TRANSFERRED_MONEY": "transaction",
    "VISITED": "location_activity",
    "sighted_at": "vehicle_sighting",
    "sent_messages_to": "communication",
    "complaint_filed_against": "complaint",
    "witnessed": "witness_statement",
}


def generate_case_events(db: Session, case: Case) -> int:
    """Derive timeline events from a case's dated relationships.

    The timeline must be navigable back to source records, so each event keeps
    relationship_id. Only relationship types that describe something that
    *happened* become events - ownership and employment are states, not events.
    """
    from app.db.models import Entity, Event, Relationship

    existing = set(db.scalars(select(Event.uid)).all())
    relationships = db.scalars(
        select(Relationship).where(
            Relationship.case_id == case.id,
            Relationship.occurred_at.is_not(None),
            Relationship.type.in_(list(EVENT_TYPE_FOR_RELATIONSHIP)),
        )
    ).all()

    created = 0
    for rel in relationships:
        uid = f"ev-{case.case_number.replace('/', '-')}-{rel.uid}"
        if uid in existing:
            continue
        source = db.get(Entity, rel.source_id)
        target = db.get(Entity, rel.target_id)
        if not source or not target:
            continue
        verb = rel.type.replace("_", " ").lower()
        amount = (rel.attributes or {}).get("amount")
        count = (rel.attributes or {}).get("call_count") or (rel.attributes or {}).get("visit_count")
        detail = ""
        if amount:
            detail = f" (Rs {amount:,})"
        elif count:
            detail = f" ({count} recorded)"
        db.add(
            Event(
                uid=uid,
                type=EVENT_TYPE_FOR_RELATIONSHIP[rel.type],
                title=f"{source.name} {verb} {target.name}{detail}",
                description=(
                    f"{source.name} - {verb} - {target.name}{detail}. "
                    f"Source: {rel.source or 'unspecified'}."
                ),
                occurred_at=rel.occurred_at,
                time_label=rel.time_label,
                entity_id=source.id,
                location_id=target.id if target.type == "location" else None,
                case_id=case.id,
                relationship_id=rel.id,
            )
        )
        created += 1
    db.flush()
    return created


def seed_all(
    reset: bool = True,
    with_corpus: bool = True,
    quiet: bool = False,
    write_credentials: bool = True,
) -> dict:
    """Build the whole database from scratch. Returns a summary.

    Pass write_credentials=False when seeding a throwaway database, so the
    handover file for the real one is left alone.
    """

    def log(message: str) -> None:
        if not quiet:
            print(message, flush=True)

    if reset:
        log("Dropping existing schema...")
        Base.metadata.drop_all(bind=engine)
    create_all()
    graph_service.invalidate()

    summary: dict = {}
    db: Session = SessionLocal()
    try:
        log("Seeding department roster...")
        credentials = seed_users(db)
        users = {u.service_id: u for u in db.scalars(select(User)).all()}
        summary["users"] = len(users)

        writer = EntityWriter(db)

        log("Seeding case NX-2026-0147 (Financial Network Investigation)...")
        core_case = seed_core_case(db, writer, users["IO-114"])

        log("Seeding case DEMO/WS-2026-0417 (Stalking & Harassment)...")
        ws_case, ws_data = seed_ws_case(db, writer, users["WSO-052"])

        log("Seeding safety zones, services, waypoints, incidents and alerts...")
        seed_safety(db, writer, ws_case, ws_data, users["WSO-052"])

        # Case teams.
        now = datetime.now(UTC)
        for case, members in (
            (core_case, [("IO-114", "Lead Investigator"), ("SI-207", "Supervisor"),
                         ("AN-331", "Analyst"), ("CFI-188", "Financial Analyst")]),
            (ws_case, [("WSO-052", "Lead Officer"), ("SI-207", "Supervisor"),
                       ("IO-114", "Investigator")]),
        ):
            for service_id, role_on_case in members:
                db.add(
                    CaseMember(
                        case_id=case.id, user_id=users[service_id].id,
                        role_on_case=role_on_case, assigned_at=now,
                    )
                )

        if with_corpus:
            log("Generating synthetic background corpus...")
            summary["corpus"] = seed_corpus(db, writer, users["AN-331"])

        log("Deriving timeline events from case relationships...")
        summary["events"] = (
            generate_case_events(db, core_case) + generate_case_events(db, ws_case)
        )

        db.commit()
        log("  committed base data")

        # ---- derived analytics ------------------------------------------
        graph_service.invalidate()

        log("Computing investigation priority scores...")
        rows = priority.compute_scores(db)
        summary["priority_scores"] = len(rows)
        db.commit()

        log("Finding entity-resolution candidates...")
        summary["resolution_candidates"] = discovery.refresh_resolution_candidates(db)
        db.commit()

        log("Detecting women-safety patterns...")
        summary["patterns"] = patterns.persist_patterns(db, case_id=ws_case.id)
        db.commit()

        # ---- notifications + opening audit trail ------------------------
        wso = users["WSO-052"]
        db.add(
            Notification(
                role_target="WOMEN_SAFETY_OFFICER",
                title="Repeated-encounter pattern awaiting review",
                body="Analytical patterns detected in case DEMO/WS-2026-0417 require investigator review.",
                severity=Priority.HIGH,
                link="/safety/patterns",
                created_at=now,
            )
        )
        db.add(
            Notification(
                role_target="INVESTIGATOR",
                title="Candidate hidden links awaiting validation",
                body="Inferred connections in case NX-2026-0147 require investigator validation.",
                severity=Priority.MEDIUM,
                link="/link-analysis",
                created_at=now,
            )
        )
        db.add(
            AuditLog(
                timestamp=now,
                actor="system",
                action="DATABASE_SEEDED",
                resource_type="database",
                result="SUCCESS",
                detail=(
                    f"Seeded {summary.get('users', 0)} users, 2 named cases and "
                    f"{summary.get('corpus', {}).get('entities', 0)} background entities. "
                    f"All non-reference data classified SYNTHETIC."
                ),
            )
        )
        db.commit()

        summary["entities"] = db.scalar(select(text("count(*)")).select_from(Entity.__table__))
        summary["cases"] = db.scalar(select(text("count(*)")).select_from(Case.__table__))
    finally:
        db.close()

    # Only write the handover file when this seed generated the passwords. With
    # SEED_PASSWORD the operator already knows the credential, and writing the
    # file anyway would clobber a real one: the path is fixed, but the database
    # being seeded is not, so seeding a throwaway database would destroy the
    # credentials for the main one.
    import os

    if os.environ.get("SEED_PASSWORD", "").strip():
        summary["credentials_file"] = None
        log("\nSEED_PASSWORD supplied - no credentials file written.")
    else:
        credentials_path = PROJECT_ROOT / "CREDENTIALS.md"
        write_credentials_file(credentials, credentials_path)
        summary["credentials_file"] = str(credentials_path)
        log(f"\nCredentials written to {credentials_path}")
    return summary


if __name__ == "__main__":
    import json

    result = seed_all(
        reset="--no-reset" not in sys.argv,
        with_corpus="--no-corpus" not in sys.argv,
    )
    print("\n" + json.dumps(result, indent=2, default=str))
