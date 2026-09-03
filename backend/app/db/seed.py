"""Database seeding.

Order matters: users -> cases -> entities -> relationships -> events ->
safety data -> derived analytics. Everything is idempotent at the top level
(seed_all wipes and rebuilds), because a half-seeded database is worse than
an empty one.

Provenance rules enforced here:
  * The two named cases are loaded verbatim from the project's own files.
  * Generated background data is written with data_classification SYNTHETIC.
  * Delhi context statistics are stored as REFERENCE and never enter analytics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
for _path in (PROJECT_ROOT / "database", PROJECT_ROOT / "ai", PROJECT_ROOT / "graph"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import seed_data as SD  # noqa: E402
from generator import CorpusGenerator  # noqa: E402

from app.core.rbac import ROLE_DESIGNATION  # noqa: E402
from app.core.security import (  # noqa: E402
    generate_password,
    hash_password,
    password_strength_errors,
)
from app.db.base import (  # noqa: E402
    AlertStatus,
    Base,
    CaseStatus,
    DataClassification,
    EvidenceStatus,
    Priority,
    SosStatus,
)
from app.db.models import (  # noqa: E402
    AuditLog,
    Case,
    CaseEntity,
    CaseMember,
    Entity,
    EntityAlias,
    Evidence,
    Event,
    IngestionJob,
    Notification,
    Record,
    Relationship,
    Report,
    ResolutionCandidate,
    SessionToken,
    User,
    Validation,
)
from app.db.models_safety import (  # noqa: E402
    EmergencyContact,
    EmergencyService,
    Incident,
    PatternDetection,
    RouteQuery,
    SafetyAlert,
    SafetyZone,
    SosAlert,
    SosStatusHistory,
    Waypoint,
    WaypointEdge,
)
from app.db.session import SessionLocal, create_all, engine  # noqa: E402

# Day 1 of the Women Safety case narrative maps onto this date so relative
# "Day N" labels sort correctly on the timeline while staying visible as
# labels in the UI.
WS_DAY_ONE = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)

CORE_CASE_NUMBER = "NX-2026-0147"
WS_CASE_NUMBER = "DEMO/WS-2026-0417"

SOURCE_DIR = PROJECT_ROOT / "database" / "source"


def _day_to_date(label: str) -> tuple[datetime | None, str | None]:
    """Map a 'Day N' or 'Day 1-14' label onto a concrete datetime."""
    if not label:
        return None, None
    text = str(label).strip()
    if text.lower().startswith("day"):
        digits = "".join(c if c.isdigit() else " " for c in text[3:]).split()
        if digits:
            return WS_DAY_ONE + timedelta(days=int(digits[0]) - 1), text
    if text.isdigit() and len(text) == 4:  # a bare year, e.g. "2024"
        return datetime(int(text), 6, 1, tzinfo=UTC), text
    return None, text


def _content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


# ============================================================ users


def seed_users(db: Session) -> dict[str, str]:
    """Create the department roster. Returns {service_id: plaintext password}.

    Passwords are generated per account and returned once so the caller can
    write them to a gitignored file. Only the scrypt hash is persisted.

    SEED_PASSWORD overrides this with one shared password for every account.
    That exists for one specific situation: a cloud deployment, where the
    generated file lands on an ephemeral disk and would be lost, leaving nobody
    able to sign in. It is a deliberate weakening - every account shares a
    credential and role separation stops being meaningful for anyone who knows
    it - so it is only ever acceptable for a demonstration instance holding
    synthetic data, and it logs a warning saying so.
    """
    import logging
    import os

    shared = os.environ.get("SEED_PASSWORD", "").strip()
    if shared:
        errors = password_strength_errors(shared)
        if errors:
            raise RuntimeError(
                "SEED_PASSWORD does not meet the password policy: " + " ".join(errors)
            )
        logging.getLogger("trinetra").warning(
            "SEED_PASSWORD is set: every seeded account shares one password. "
            "Acceptable only for a synthetic-data demonstration instance."
        )

    credentials: dict[str, str] = {}
    now = datetime.now(UTC)
    for member in SD.DEPARTMENT_ROSTER:
        password = shared or generate_password(16)
        credentials[member["service_id"]] = password
        db.add(
            User(
                service_id=member["service_id"],
                full_name=member["full_name"],
                role=member["role"],
                designation=member["designation"],
                unit=member["unit"],
                email=member["email"],
                extension=member["extension"],
                password_hash=hash_password(password),
                must_change_password=False,
                is_active=True,
                password_changed_at=now,
            )
        )
    db.flush()
    return credentials


def write_credentials_file(credentials: dict[str, str], path: Path) -> None:
    """Write the generated credentials to a gitignored operator handover file."""
    roster = {m["service_id"]: m for m in SD.DEPARTMENT_ROSTER}
    lines = [
        "# TRINETRA - Generated Account Credentials",
        "",
        "> **This file is gitignored and must never be committed.**",
        "> Passwords were generated at seed time and are stored in the database",
        "> only as scrypt hashes. This is the sole plaintext copy.",
        "> Re-running the seed generates entirely new passwords.",
        "",
        f"Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        "",
        "| Service ID | Name | Designation | Role | Password |",
        "|---|---|---|---|---|",
    ]
    for service_id, password in credentials.items():
        member = roster[service_id]
        lines.append(
            f"| `{service_id}` | {member['full_name']} | {member['designation']} "
            f"| `{member['role']}` | `{password}` |"
        )
    lines += [
        "",
        "## Access notes",
        "",
        "- Sign in with the **Service ID**, not the name or email.",
        "- Five consecutive failed attempts lock the account for 15 minutes.",
        "- Roles are enforced by the backend on every endpoint; signing in as a",
        "  lower-privileged account genuinely returns 403 rather than hiding buttons.",
        "",
        "## Role capabilities",
        "",
    ]
    from app.core.rbac import permissions_for

    for role, designation in ROLE_DESIGNATION.items():
        perms = sorted(permissions_for(role))
        lines.append(f"- **{designation}** (`{role}`) - {len(perms)} permissions")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================ entities


class EntityWriter:
    """Creates entities and relationships while keeping a uid -> row map."""

    def __init__(self, db: Session, flush_every: int = 1) -> None:
        self.db = db
        self.by_uid: dict[str, Entity] = {}
        self._rel_seq = 0
        # A flush is a network round-trip. Flushing per row is fine against a
        # local file but costs minutes against a remote database, so bulk
        # loading raises this. Case seeding leaves it at 1, where later rows
        # depend on the ids of earlier ones.
        self.flush_every = flush_every
        self._pending = 0

    def _maybe_flush(self) -> None:
        self._pending += 1
        if self._pending >= self.flush_every:
            self.db.flush()
            self._pending = 0

    def entity(
        self,
        uid: str,
        entity_type: str,
        name: str,
        aliases: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
        source: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        classification: str = DataClassification.SYNTHETIC,
    ) -> Entity:
        from trinetra_nlp.engine import normalize

        row = Entity(
            uid=uid,
            type=entity_type,
            name=name,
            normalized_name=normalize(name, entity_type),
            attributes=attributes or {},
            source=source,
            latitude=latitude,
            longitude=longitude,
            data_classification=classification,
        )
        self.db.add(row)
        # Appending to the relationship lets SQLAlchemy fill entity_id on the
        # next flush, so the alias does not force a round-trip of its own.
        for alias in aliases or []:
            row.aliases.append(
                EntityAlias(
                    alias=alias,
                    normalized_alias=normalize(alias, entity_type),
                    source=source,
                )
            )
        self._maybe_flush()
        self.by_uid[uid] = row
        return row

    def relationship(
        self,
        source_uid: str,
        target_uid: str,
        rel_type: str,
        *,
        source_ref: str | None = None,
        occurred_at: datetime | None = None,
        time_label: str | None = None,
        confidence: float = 1.0,
        status: str = EvidenceStatus.OBSERVED,
        attributes: dict[str, Any] | None = None,
        derivation: dict[str, Any] | None = None,
        case: Case | None = None,
        classification: str = DataClassification.SYNTHETIC,
    ) -> Relationship | None:
        source = self.by_uid.get(source_uid)
        target = self.by_uid.get(target_uid)
        if source is None or target is None:
            return None
        self._rel_seq += 1
        row = Relationship(
            uid=f"r-{self._rel_seq:06d}",
            source_id=source.id,
            target_id=target.id,
            type=rel_type,
            evidence_status=status,
            confidence=confidence,
            source=source_ref,
            occurred_at=occurred_at,
            time_label=time_label,
            attributes=attributes or {},
            derivation=derivation or {},
            case_id=case.id if case else None,
            data_classification=classification,
        )
        self.db.add(row)
        self._maybe_flush()
        return row


# ============================================================ core case


def seed_core_case(db: Session, writer: EntityWriter, owner: User) -> Case:
    """Case NX-2026-0147, from the project's own dataset."""
    case = Case(
        case_number=CORE_CASE_NUMBER,
        title="Financial Network Investigation",
        description=(
            "Investigation into a suspected freight-and-trading network moving "
            "funds between logistics and trading entities across the NCR. "
            "Source records comprise FIRs, call detail records, bank statements "
            "and surveillance reports."
        ),
        status=CaseStatus.UNDER_INVESTIGATION,
        priority=Priority.HIGH,
        module="NETWORK",
        owner_id=owner.id,
        opened_at=datetime(2026, 1, 10, tzinfo=UTC),
    )
    db.add(case)
    db.flush()

    for uid, etype, name, aliases, attrs in SD.CORE_ENTITIES:
        coords = SD.LOCATION_COORDS.get(uid)
        writer.entity(
            uid, etype, name, aliases, attrs,
            source="Case file NX-2026-0147",
            latitude=coords[0] if coords else None,
            longitude=coords[1] if coords else None,
        )
        db.add(
            CaseEntity(
                case_id=case.id,
                entity_id=writer.by_uid[uid].id,
                added_at=case.opened_at,
                added_by_id=owner.id,
            )
        )

    case.lead_entity_id = writer.by_uid["p1"].id

    evidence_seq = 0
    for src, tgt, rel_type, ref, date_text, confidence, attrs in SD.CORE_RELATIONSHIPS:
        occurred = datetime.fromisoformat(date_text).replace(tzinfo=UTC)
        rel = writer.relationship(
            src, tgt, rel_type,
            source_ref=ref, occurred_at=occurred, confidence=confidence,
            attributes=attrs, case=case,
        )
        if rel is None:
            continue
        evidence_seq += 1
        source_type = (
            "FIR" if ref.startswith("FIR") else
            "CDR" if ref.startswith("CDR") else
            "Financial" if "Bank" in ref else
            "Surveillance" if "Surveillance" in ref else "Records"
        )
        db.add(
            Evidence(
                evidence_ref=f"EV-NX-{evidence_seq:04d}",
                source=ref,
                source_type=source_type,
                description=(
                    f"{writer.by_uid[src].name} - {rel_type} - {writer.by_uid[tgt].name}"
                ),
                occurred_at=occurred,
                entity_id=writer.by_uid[src].id,
                relationship_id=rel.id,
                case_id=case.id,
                confidence=confidence,
                status=EvidenceStatus.OBSERVED,
            )
        )

    # ---- Inferred candidate links, from the project's own analysis --------
    # Supporting relationship ids are looked up from what was actually written,
    # so the evidence chain is real rather than a hardcoded list of labels.
    def find_rel(a: str, b: str, rel_type: str) -> Relationship | None:
        ea, eb = writer.by_uid.get(a), writer.by_uid.get(b)
        if not ea or not eb:
            return None
        return db.scalars(
            select(Relationship).where(
                Relationship.type == rel_type,
                Relationship.source_id.in_([ea.id, eb.id]),
                Relationship.target_id.in_([ea.id, eb.id]),
            )
        ).first()

    support_a = [
        r.id for r in (
            find_rel("p1", "p2", "CALLED"),
            find_rel("p2", "p3", "CALLED"),
            find_rel("p3", "o2", "ASSOCIATED_WITH"),
            find_rel("t1", "o1", "ASSOCIATED_WITH"),
            find_rel("t2", "o2", "ASSOCIATED_WITH"),
            find_rel("p2", "l2", "VISITED"),
            find_rel("p3", "l2", "VISITED"),
        ) if r
    ]
    writer.relationship(
        "p1", "p3", "CONNECTED_TO",
        source_ref="Derived (graph inference)",
        occurred_at=datetime(2026, 1, 24, tzinfo=UTC),
        confidence=0.68,
        status=EvidenceStatus.INFERRED,
        case=case,
        derivation={
            "reason": (
                "No direct call, meeting or transaction links Rahul Sharma and "
                "Vikram Singh. Both share a common associate (Amit Verma), "
                "overlapping presence in Delhi, and a financial trail between "
                "organisations each is connected to (Shivam Logistics / Alpha Trading)."
            ),
            "supporting_relationship_ids": support_a,
            "method": "common-neighbour + shared-location + financial-path analysis",
            "factors": [
                {"label": "Shared intermediary", "detail": "Amit Verma connects both parties"},
                {"label": "Location overlap", "detail": "Both recorded in Delhi"},
                {"label": "Financial path", "detail": "Shivam Logistics / Alpha Trading transfers"},
            ],
        },
    )

    support_b = [
        r.id for r in (
            find_rel("p1", "p4", "ASSOCIATED_WITH"),
            find_rel("p1", "p2", "MET"),
            find_rel("p2", "p3", "CALLED"),
        ) if r
    ]
    writer.relationship(
        "p4", "p3", "CONNECTED_TO",
        source_ref="Derived (graph inference)",
        occurred_at=datetime(2026, 1, 24, tzinfo=UTC),
        confidence=0.42,
        status=EvidenceStatus.INFERRED,
        case=case,
        derivation={
            "reason": (
                "Neha Sharma has no observed direct contact with Vikram Singh, but "
                "is linked through two intermediate relationships (Rahul Sharma "
                "and Amit Verma)."
            ),
            "supporting_relationship_ids": support_b,
            "method": "two-hop path analysis",
            "factors": [
                {"label": "Path length", "detail": "Shortest connection is 3 hops"},
                {"label": "Corroboration", "detail": "No independent signal"},
            ],
        },
    )
    return case


# ============================================================ women safety case


def seed_ws_case(db: Session, writer: EntityWriter, owner: User) -> Case:
    """Case DEMO/WS-2026-0417, loaded verbatim from the source JSON."""
    source_file = SOURCE_DIR / "TRINETRA_DEMO_WS-2026-0417.json"
    data = json.loads(source_file.read_text(encoding="utf-8"))

    case = Case(
        case_number=WS_CASE_NUMBER,
        title="Stalking & Harassment Investigation",
        description=data["metadata"]["title"] + " - " + data["metadata"]["purpose"],
        status=CaseStatus.UNDER_INVESTIGATION,
        priority=Priority.CRITICAL,
        module="WOMEN_SAFETY",
        owner_id=owner.id,
        opened_at=WS_DAY_ONE,
    )
    db.add(case)
    db.flush()

    type_map = {
        "person": "person", "phone": "phone", "social_handle": "social",
        "vehicle": "vehicle", "transaction": "transaction", "location": "location",
        "event": "event", "case": "case_record",
    }
    role_labels = {
        "victim": "Victim",
        "suspect_primary": "Primary Suspect",
        "linked_identity": "Linked Identity",
        "witness": "Witness",
    }

    for item in data["entities"]:
        uid = item["id"]
        entity_type = type_map.get(item["type"], item["type"])
        name = item.get("alias") or item.get("value") or item.get("name") or uid
        attributes: dict[str, Any] = {}
        if item.get("role"):
            attributes["role"] = role_labels.get(item["role"], item["role"])
        if "registered" in item:
            attributes["registered"] = item["registered"]
        if item.get("name") and item.get("alias"):
            attributes["case_label"] = item["name"]

        # Identifiers that let entity resolution find the S1/S2 alias link the
        # way it would in a real deployment: through shared hard identifiers,
        # not through a hardcoded answer.
        if uid in ("S1", "S2"):
            attributes["id_proof"] = "IDP-4471"
            attributes["vehicle"] = "DL0XXX4471"

        coords = SD.LOCATION_COORDS.get(uid)
        writer.entity(
            uid, entity_type, name,
            aliases=[item["name"]] if item.get("name") and item.get("alias") else [],
            attributes=attributes,
            source=item.get("source"),
            latitude=coords[0] if coords else None,
            longitude=coords[1] if coords else None,
        )
        db.add(
            CaseEntity(
                case_id=case.id,
                entity_id=writer.by_uid[uid].id,
                role_in_case=attributes.get("role"),
                added_at=WS_DAY_ONE,
                added_by_id=owner.id,
            )
        )

    case.lead_entity_id = writer.by_uid["S1"].id

    # Relationships, preserving the source file's observed/inferred marking.
    rel_rows: dict[str, Relationship] = {}
    evidence_seq = 0
    for item in data["relationships"]:
        occurred, label = _day_to_date(item.get("time", ""))
        status = (
            EvidenceStatus.OBSERVED
            if item["evidence_type"] == "observed"
            else EvidenceStatus.INFERRED
        )
        rel = writer.relationship(
            item["from"], item["to"], item["relationship"],
            source_ref=item.get("source"),
            occurred_at=occurred,
            time_label=label,
            confidence=float(item["confidence"]),
            status=status,
            case=case,
        )
        if rel is None:
            continue
        rel_rows[item["id"]] = rel
        evidence_seq += 1
        db.add(
            Evidence(
                evidence_ref=f"EV-WS-{evidence_seq:04d}",
                source=item.get("source", "Case file"),
                source_type="FIR" if "FIR" in (item.get("source") or "") else "Records",
                description=(
                    f"{writer.by_uid[item['from']].name} - {item['relationship']} - "
                    f"{writer.by_uid[item['to']].name}"
                ),
                occurred_at=occurred,
                entity_id=writer.by_uid[item["from"]].id,
                relationship_id=rel.id,
                case_id=case.id,
                confidence=float(item["confidence"]),
                status=status,
            )
        )

    # Attach derivation chains to the inferred links, referencing the real rows.
    derivations = {
        "R003": (
            ["R004", "R005"],
            "PH2 (+91-70xxxx4482) is unregistered. Call-pattern correlation with S1's "
            "registered number, plus a SIM-purchase record whose ID proof matches S1, "
            "indicates probable use by S1. This is a candidate lead, not a registered "
            "ownership record.",
            "call-pattern correlation + KYC identifier match",
        ),
        "R006": (
            ["R007"],
            "Entity resolution matched R. Verma (S1) to a prior identity, S. Mehta (S2), "
            "named in a stalking FIR filed in a different district in 2024 - a link the "
            "two siloed case records did not previously share.",
            "entity resolution (shared identifier + case linkage)",
        ),
        "R016": (
            ["R015", "R003"],
            "Platform metadata for the handle @user_4471 correlates with the unregistered "
            "number PH2 through account-registration and device-fingerprint overlap. "
            "Lower-confidence candidate link, pending corroboration.",
            "platform metadata correlation",
        ),
    }
    for rel_id, (support_ids, reason, method) in derivations.items():
        row = rel_rows.get(rel_id)
        if not row:
            continue
        row.derivation = {
            "reason": reason,
            "method": method,
            "supporting_relationship_ids": [
                rel_rows[s].id for s in support_ids if s in rel_rows
            ],
        }

    # Timeline events.
    for item in data["events"]:
        occurred, label = _day_to_date(item.get("time", ""))
        entity = writer.by_uid.get(item.get("entity", ""))
        location = writer.by_uid.get(item.get("location", ""))
        db.add(
            Event(
                uid=f"ws-{item['event_id']}",
                type=item["type"],
                title=item["description"][:180],
                description=item["description"],
                occurred_at=occurred,
                time_label=label,
                entity_id=entity.id if entity else None,
                location_id=location.id if location else None,
                case_id=case.id,
            )
        )
    return case, data


# ============================================================ safety data


def seed_safety(
    db: Session, writer: EntityWriter, ws_case: Case, ws_data: dict, wso: User
) -> None:
    zones: dict[str, SafetyZone] = {}
    for item in SD.SAFETY_ZONES:
        zone = SafetyZone(**item)
        db.add(zone)
        db.flush()
        zones[item["zone_ref"]] = zone

    services: dict[str, EmergencyService] = {}
    for item in SD.EMERGENCY_SERVICES:
        payload = dict(item)
        zone_ref = payload.pop("zone_ref", None)
        service = EmergencyService(**payload, zone_id=zones[zone_ref].id if zone_ref else None)
        db.add(service)
        db.flush()
        services[item["service_ref"]] = service

    # -- routable waypoint network ------------------------------------
    # A small explicit road graph over the case geography. Real deployments
    # would source this from a mapping provider; see docs/INTEGRATIONS.md.
    waypoint_defs = [
        ("WP-LOC1", "Victim Residence (LOC1)", 28.7196, 77.1025, "ZONE-01", True, "LOC1"),
        ("WP-LOC2", "Victim Workplace (LOC2)", 28.6950, 77.1400, "ZONE-02", True, "LOC2"),
        ("WP-LOC3", "Confrontation Site (LOC3)", 28.7080, 77.1230, "ZONE-03", True, "LOC3"),
        ("WP-MKT", "Central Market", 28.6890, 77.1180, "ZONE-04", True, None),
        ("WP-SEC4", "Sector 4 Crossing", 28.7300, 77.1320, "ZONE-05", True, None),
        ("WP-N1", "Ring Road Junction North", 28.7180, 77.1210, "ZONE-01", False, None),
        ("WP-N2", "Link Road Chowk", 28.7060, 77.1090, "ZONE-01", False, None),
        ("WP-N3", "Market Underpass", 28.6980, 77.1250, "ZONE-04", False, None),
        ("WP-N4", "Metro Station Approach", 28.7020, 77.1360, "ZONE-02", False, None),
        ("WP-N5", "Service Lane East", 28.7130, 77.1310, "ZONE-03", False, None),
        ("WP-N6", "Canal Road Bend", 28.7240, 77.1180, "ZONE-05", False, None),
    ]
    waypoints: dict[str, Waypoint] = {}
    for ref, name, lat, lng, zone_ref, endpoint, entity_uid in waypoint_defs:
        entity = writer.by_uid.get(entity_uid) if entity_uid else None
        wp = Waypoint(
            waypoint_ref=ref, name=name, latitude=lat, longitude=lng,
            zone_id=zones[zone_ref].id, is_endpoint=endpoint,
            entity_id=entity.id if entity else None,
            lit=ref not in ("WP-N3", "WP-N5"),
        )
        db.add(wp)
        db.flush()
        waypoints[ref] = wp

    from trinetra_graph.algorithms import haversine_km

    segments = [
        ("WP-LOC1", "WP-N1"), ("WP-LOC1", "WP-N2"), ("WP-N1", "WP-N5"),
        ("WP-N1", "WP-N6"), ("WP-N2", "WP-N3"), ("WP-N3", "WP-MKT"),
        ("WP-MKT", "WP-N4"), ("WP-N4", "WP-LOC2"), ("WP-N5", "WP-LOC3"),
        ("WP-LOC3", "WP-N4"), ("WP-N6", "WP-SEC4"), ("WP-SEC4", "WP-N5"),
        ("WP-N3", "WP-N4"), ("WP-N2", "WP-MKT"), ("WP-LOC3", "WP-LOC2"),
    ]
    for a, b in segments:
        wa, wb = waypoints[a], waypoints[b]
        distance = haversine_km(wa.latitude, wa.longitude, wb.latitude, wb.longitude)
        db.add(WaypointEdge(from_id=wa.id, to_id=wb.id, distance_km=round(distance, 4)))
        db.add(WaypointEdge(from_id=wb.id, to_id=wa.id, distance_km=round(distance, 4)))

    # -- incidents from the source case file ---------------------------
    zone_for_location = {
        "LOC1": "ZONE-01", "LOC2": "ZONE-02", "LOC3": "ZONE-03",
        "LOC1→LOC2": "ZONE-02", "OTHER_DISTRICT": None,
    }
    for item in ws_data["incidents"]:
        occurred, label = _day_to_date(item.get("time", ""))
        location_key = item.get("location", "")
        location_entity = writer.by_uid.get(location_key)
        zone_ref = zone_for_location.get(location_key)
        zone = zones.get(zone_ref) if zone_ref else None
        subject = writer.by_uid.get(item.get("subject_entity", ""))
        coords = SD.LOCATION_COORDS.get(location_key)
        descriptors: dict[str, Any] = {}
        if "VEH1" in (item.get("description", "") + location_key):
            descriptors["vehicle"] = "DL-0X-XX-4471"
        if "PH2" in item.get("description", ""):
            descriptors["device"] = "+91-70xxxx4482"

        db.add(
            Incident(
                incident_ref=item["incident_id"],
                type=item["type"],
                description=item["description"],
                priority=item["priority"],
                status=item["status"],
                occurred_at=occurred,
                time_label=label,
                hour_of_day=occurred.hour if occurred else None,
                case_id=ws_case.id if item["case_id"] == WS_CASE_NUMBER else None,
                subject_entity_id=subject.id if subject else None,
                location_entity_id=location_entity.id if location_entity else None,
                zone_id=zone.id if zone else None,
                latitude=coords[0] if coords else None,
                longitude=coords[1] if coords else None,
                location_text=coords[2] if coords else location_key,
                descriptors=descriptors,
                reported_by_id=wso.id,
            )
        )

    # -- emergency contacts for the case subject -----------------------
    victim = writer.by_uid.get("V1")
    if victim:
        for order, (name, relation, phone) in enumerate(
            [
                ("Emergency Contact 1", "Family", "+91-98xxxx0001"),
                ("Emergency Contact 2", "Colleague", "+91-98xxxx0002"),
            ],
            start=1,
        ):
            db.add(
                EmergencyContact(
                    owner_entity_id=victim.id, name=name, relation=relation,
                    phone=phone, priority_order=order,
                )
            )

    # -- SOS alert from the source file --------------------------------
    sos_source = ws_data.get("sos", {})
    if sos_source:
        raised = WS_DAY_ONE + timedelta(days=15, hours=9)
        sos = SosAlert(
            alert_ref=sos_source["alert_id"],
            status=SosStatus.ASSIGNED,
            priority=Priority.CRITICAL,
            subject_entity_id=victim.id if victim else None,
            subject_name=victim.name if victim else "Case subject",
            raised_at=raised,
            latitude=SD.LOCATION_COORDS["LOC2"][0],
            longitude=SD.LOCATION_COORDS["LOC2"][1],
            location_text=sos_source.get("location", "Simulated location"),
            location_source="SIMULATED",
            zone_id=zones["ZONE-02"].id,
            case_id=ws_case.id,
            assigned_unit_id=services["ES-003"].id,
            assigned_officer_id=wso.id,
            notes=sos_source.get("note"),
            contacts_notified=sos_source.get("contacts", []),
        )
        db.add(sos)
        db.flush()
        db.add(
            SosStatusHistory(
                alert_id=sos.id, from_status=None, to_status=SosStatus.RECEIVED,
                changed_at=raised, note="Alert received by the operations console.",
            )
        )
        db.add(
            SosStatusHistory(
                alert_id=sos.id, from_status=SosStatus.RECEIVED,
                to_status=SosStatus.ASSIGNED, changed_by_id=wso.id,
                changed_at=raised + timedelta(minutes=3),
                note=f"Assigned to {services['ES-003'].name}.",
            )
        )

    # -- live safety alerts from the source file -----------------------
    status_map = {
        "UNDER_REVIEW": AlertStatus.ACKNOWLEDGED,
        "ESCALATED": AlertStatus.RESPONDING,
        "PENDING_VALIDATION": AlertStatus.NEW,
    }
    for item in ws_data.get("alerts", []):
        occurred, label = _day_to_date(item.get("time", ""))
        db.add(
            SafetyAlert(
                alert_ref=item["alert_id"],
                module=item["module"],
                priority=item["priority"],
                status=status_map.get(item["status"], AlertStatus.NEW),
                message=item["message"],
                detail=(
                    "Imported from the case file. Requires authorised investigator "
                    "review before any action."
                ),
                raised_at=occurred or WS_DAY_ONE,
                time_label=label,
                case_id=ws_case.id,
                assigned_to_id=wso.id if item["status"] != "PENDING_VALIDATION" else None,
                supporting={"origin": "case file", "original_status": item["status"]},
            )
        )
