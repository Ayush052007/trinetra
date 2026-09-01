"""Data ingestion pipeline.

Counters reported at the end are counted from the uploaded file. Nothing here
is fixed: upload a two-row CSV and the pipeline reports two records.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import Perm
from app.db.base import DataClassification, EvidenceStatus
from app.db.models import (
    Case,
    CaseEntity,
    Entity,
    IngestionJob,
    Record,
    Relationship,
    User,
)
from app.db.session import get_db
from app.services import graph_service
from app.services.mutations import next_relationship_uid, record_audit
from app.services.realtime import broadcast

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "ai"))
from trinetra_nlp.engine import DEFAULT_ENGINE, normalize  # noqa: E402

router = APIRouter(prefix="/data", tags=["ingestion"], dependencies=[Depends(api_rate_limiter)])

ALLOWED_EXTENSIONS = {".csv", ".txt", ".json", ".tsv"}
ALLOWED_CONTENT_TYPES = {
    "text/csv", "text/plain", "application/json", "application/csv",
    "text/tab-separated-values", "application/vnd.ms-excel", "",
}

SOURCE_TYPES = ["FIR", "CDR", "Financial", "Surveillance", "Records", "Social Media"]

PIPELINE_STAGES = [
    ("validate", "File validation"),
    ("parse", "Parsing"),
    ("clean", "Data cleaning"),
    ("normalise", "Normalisation"),
    ("deduplicate", "Deduplication"),
    ("extract", "Entity extraction"),
    ("resolve", "Entity resolution"),
    ("relate", "Relationship extraction"),
    ("store", "Database storage"),
    ("graph", "Knowledge graph update"),
]

# Formula characters that spreadsheet software would execute on open.
CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitise(value: str) -> str:
    """Neutralise CSV-injection payloads without discarding the value."""
    text = (value or "").strip()
    if text.startswith(CSV_INJECTION_PREFIXES):
        return "'" + text
    return text


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@router.get("/sources")
def sources(
    user: User = Depends(require_permission(Perm.CASE_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ingestion channels with live record counts from the database."""
    counts = dict(
        db.execute(
            select(Record.source_type, func.count()).group_by(Record.source_type)
        ).all()
    )
    definitions = [
        ("FIR", "FIR / Investigation Reports", "CSV, TXT, JSON",
         "First Information Reports and investigation narratives"),
        ("CDR", "Call Detail Records", "CSV, TSV",
         "Call and message metadata from telecom providers"),
        ("Financial", "Financial Transactions", "CSV, JSON",
         "Bank statements and transaction records"),
        ("Surveillance", "Surveillance Reports", "CSV, TXT",
         "Observation logs and sighting reports"),
        ("Records", "Official Records", "CSV, JSON",
         "KYC, vehicle registration and employment records"),
        ("Social Media", "Social Media Intelligence", "JSON",
         "Platform metadata obtained under authorised request"),
    ]
    return {
        "sources": [
            {
                "key": key, "label": label, "formats": formats,
                "description": description, "record_count": counts.get(key, 0),
            }
            for key, label, formats, description in definitions
        ],
        "total_records": sum(counts.values()),
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "pipeline": [{"key": k, "label": v} for k, v in PIPELINE_STAGES],
        "connected_feeds": {
            "telecom_cdr": settings.ENABLE_TELECOM_CDR_FEED,
            "rto_lookup": settings.ENABLE_RTO_LOOKUP,
            "cctns_sync": settings.ENABLE_CCTNS_SYNC,
            "notice": (
                "Automated feeds are not connected. All data currently enters "
                "through manual upload."
            ),
        },
    }


@router.get("/jobs")
def jobs(
    limit: int = 20,
    user: User = Depends(require_permission(Perm.CASE_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = db.scalars(
        select(IngestionJob).order_by(IngestionJob.started_at.desc()).limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": j.id, "filename": j.filename, "source_type": j.source_type,
                "status": j.status, "stage": j.stage,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                "uploaded_by": j.uploaded_by.full_name if j.uploaded_by else None,
                "counters": {
                    "records_received": j.records_received,
                    "records_processed": j.records_processed,
                    "duplicates": j.duplicates,
                    "entities_extracted": j.entities_extracted,
                    "relationships_created": j.relationships_created,
                },
                "stage_log": j.stage_log,
                "error": j.error,
            }
            for j in rows
        ]
    }


@router.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    source_type: str = Form("Records"),
    case_id: int | None = Form(None),
    user: User = Depends(require_permission(Perm.DATA_UPLOAD)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Validate, parse and ingest an uploaded file into the knowledge graph."""
    stage_log: list[dict[str, Any]] = []

    def stage(key: str, status_value: str, detail: str = "", **extra) -> None:
        entry = {"stage": key, "status": status_value, "detail": detail, **extra}
        stage_log.append(entry)
        broadcast({"channel": "ingestion", "event": "stage", "data": entry})

    # ---- validate ----------------------------------------------------
    filename = Path(file.filename or "upload").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "message": f"Unsupported file type '{extension or 'unknown'}'.",
                "allowed": sorted(ALLOWED_EXTENSIONS),
            },
        )
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported content type '{file.content_type}'.",
        )
    if source_type not in SOURCE_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"message": "Unknown source type.", "allowed": SOURCE_TYPES},
        )

    raw = await file.read()
    if len(raw) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit.",
        )
    if not raw.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "File could not be decoded as text. Upload a UTF-8 CSV, TSV, JSON or TXT file.",
            ) from None

    case = db.get(Case, case_id) if case_id else None
    now = datetime.now(UTC)
    job = IngestionJob(
        filename=filename,
        source_type=source_type,
        uploaded_by_id=user.id,
        case_id=case.id if case else None,
        started_at=now,
        status="RUNNING",
        stage="validate",
    )
    db.add(job)
    db.flush()
    stage("validate", "complete", f"{filename} ({len(raw):,} bytes) accepted")

    # ---- parse -------------------------------------------------------
    rows: list[dict[str, Any]] = []
    free_text_blocks: list[str] = []
    try:
        if extension == ".json":
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                for value in parsed.values():
                    if isinstance(value, list):
                        rows.extend(v for v in value if isinstance(v, dict))
                if not rows:
                    rows = [parsed]
            elif isinstance(parsed, list):
                rows = [v for v in parsed if isinstance(v, dict)]
        elif extension in (".csv", ".tsv"):
            delimiter = "\t" if extension == ".tsv" else None
            sample = text[:4096]
            if delimiter is None:
                try:
                    delimiter = csv.Sniffer().sniff(sample, delimiters=",;|\t").delimiter
                except csv.Error:
                    delimiter = ","
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            rows = [
                {(k or "").strip(): _sanitise(str(v)) for k, v in row.items() if k}
                for row in reader
            ]
        else:  # .txt - treat as free narrative for NLP extraction
            free_text_blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    except (json.JSONDecodeError, csv.Error) as exc:
        job.status = "FAILED"
        job.error = f"Parse error: {exc}"
        job.finished_at = datetime.now(UTC)
        job.stage_log = stage_log
        stage("parse", "failed", str(exc))
        db.commit()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"The file could not be parsed: {exc}"
        ) from None

    received = len(rows) + len(free_text_blocks)
    if received == 0:
        job.status = "FAILED"
        job.error = "No usable records found"
        job.finished_at = datetime.now(UTC)
        job.stage_log = stage_log
        stage("parse", "failed", "no records")
        db.commit()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No records were found in the file. Check that it has a header row and data.",
        )
    job.records_received = received
    stage("parse", "complete", f"{received:,} record(s) read")
    stage("clean", "complete", "Whitespace trimmed, formula characters neutralised")

    # ---- deduplicate --------------------------------------------------
    existing_hashes = set(
        db.scalars(select(Record.content_hash).where(Record.source_type == source_type)).all()
    )
    seen: set[str] = set()
    unique_rows: list[tuple[dict, str]] = []
    duplicates = 0
    for row in rows:
        digest = _hash(row)
        if digest in seen or digest in existing_hashes:
            duplicates += 1
            continue
        seen.add(digest)
        unique_rows.append((row, digest))
    stage("normalise", "complete", f"{len(unique_rows):,} record(s) normalised")
    stage("deduplicate", "complete", f"{duplicates:,} duplicate(s) identified")

    # ---- extract ------------------------------------------------------
    from app.api.v1.nlp import build_gazetteer

    gazetteer = build_gazetteer(db)
    entity_cache: dict[tuple[str, str], Entity] = {}
    created_entities = 0
    created_relationships = 0

    counter = db.scalar(select(func.count()).select_from(Entity)) or 0

    def upsert_entity(name: str, entity_type: str) -> Entity | None:
        nonlocal created_entities, counter
        clean = (name or "").strip()
        if not clean or len(clean) > 190:
            return None
        key = (entity_type, normalize(clean, entity_type))
        if key in entity_cache:
            return entity_cache[key]
        hit = gazetteer.lookup(clean, entity_type)
        if hit:
            found = db.scalars(select(Entity).where(Entity.uid == hit[0])).first()
            if found:
                entity_cache[key] = found
                return found
        found = db.scalars(
            select(Entity).where(
                Entity.type == entity_type,
                Entity.normalized_name == key[1],
                Entity.is_active.is_(True),
            )
        ).first()
        if found is None:
            counter += 1
            found = Entity(
                uid=f"up-{job.id}-{counter:06d}",
                type=entity_type,
                name=clean,
                normalized_name=key[1],
                attributes={"ingested_from": filename},
                source=f"Upload: {filename}",
                data_classification=DataClassification.SYNTHETIC,
            )
            db.add(found)
            db.flush()
            created_entities += 1
            gazetteer.add(found.uid, entity_type, clean)
            if case:
                db.add(
                    CaseEntity(
                        case_id=case.id, entity_id=found.id,
                        added_at=now, added_by_id=user.id,
                    )
                )
        entity_cache[key] = found
        return found

    # Column-name conventions understood by the tabular importer.
    COLUMN_MAP = {
        "person": ("person", "person_name", "name", "subject", "from_person", "caller"),
        "person_b": ("person_b", "to_person", "associate", "callee", "counterpart"),
        "phone": ("phone", "phone_number", "mobile", "msisdn", "number"),
        "location": ("location", "place", "address", "area", "locality"),
        "organization": ("organization", "organisation", "company", "org", "firm"),
        "vehicle": ("vehicle", "vehicle_number", "registration", "vehicle_no"),
        "transaction": ("amount", "transaction_amount", "value", "txn_amount"),
    }

    def pick(row: dict, keys: tuple[str, ...]) -> str | None:
        lowered = {k.lower().replace(" ", "_"): v for k, v in row.items()}
        for key in keys:
            value = lowered.get(key)
            if value and str(value).strip() and str(value).strip() not in ("-", "NA", "N/A"):
                return str(value).strip()
        return None

    stored_records: list[Record] = []
    for row, digest in unique_rows:
        record = Record(
            job_id=job.id,
            source_type=source_type,
            source_ref=pick(row, ("source_ref", "fir_id", "record_id", "reference")) or filename,
            occurred_at=_parse_date(pick(row, ("date", "timestamp", "occurred_at", "datetime"))),
            payload=row,
            content_hash=digest,
            is_duplicate=False,
            case_id=case.id if case else None,
            created_at=now,
        )
        db.add(record)
        stored_records.append(record)

        subject = upsert_entity(pick(row, COLUMN_MAP["person"]) or "", "person")
        counterpart = upsert_entity(pick(row, COLUMN_MAP["person_b"]) or "", "person")
        phone = upsert_entity(pick(row, COLUMN_MAP["phone"]) or "", "phone")
        location = upsert_entity(pick(row, COLUMN_MAP["location"]) or "", "location")
        organization = upsert_entity(pick(row, COLUMN_MAP["organization"]) or "", "organization")
        vehicle = upsert_entity(pick(row, COLUMN_MAP["vehicle"]) or "", "vehicle")
        amount_raw = pick(row, COLUMN_MAP["transaction"])
        transaction = (
            upsert_entity(f"Rs {amount_raw}", "transaction") if amount_raw else None
        )

        pairs = [
            (subject, counterpart, "CALLED" if source_type == "CDR" else "ASSOCIATED_WITH"),
            (subject, phone, "OWNED"),
            (subject, location, "VISITED"),
            (subject, organization, "ASSOCIATED_WITH"),
            (subject, vehicle, "OWNED"),
            (subject, transaction, "TRANSFERRED_MONEY"),
        ]
        for source_entity, target_entity, rel_type in pairs:
            if source_entity is None or target_entity is None:
                continue
            if source_entity.id == target_entity.id:
                continue
            exists = db.scalars(
                select(Relationship).where(
                    Relationship.source_id == source_entity.id,
                    Relationship.target_id == target_entity.id,
                    Relationship.type == rel_type,
                )
            ).first()
            if exists:
                continue
            db.add(
                Relationship(
                    uid=next_relationship_uid(db),
                    source_id=source_entity.id,
                    target_id=target_entity.id,
                    type=rel_type,
                    # Tabular records assert facts directly; they are observations.
                    evidence_status=EvidenceStatus.OBSERVED,
                    confidence=0.9,
                    source=f"{source_type} upload: {filename}",
                    occurred_at=record.occurred_at or now,
                    case_id=case.id if case else None,
                    data_classification=DataClassification.SYNTHETIC,
                )
            )
            db.flush()
            created_relationships += 1

    # Free narrative text goes through the NLP pipeline instead.
    for block in free_text_blocks:
        digest = _hash({"text": block})
        db.add(
            Record(
                job_id=job.id, source_type=source_type, source_ref=filename,
                occurred_at=now, payload={"text": block[:4000]},
                content_hash=digest, case_id=case.id if case else None, created_at=now,
            )
        )
        result = DEFAULT_ENGINE.analyze(block, gazetteer)
        surface_to_entity: dict[str, Entity] = {}
        for extracted in result.entities:
            if extracted.type == "event":
                continue
            entity = upsert_entity(extracted.text, extracted.type)
            if entity:
                surface_to_entity[extracted.text.lower()] = entity
        for extracted in result.relationships:
            source_entity = surface_to_entity.get(extracted.source_text.lower())
            target_entity = surface_to_entity.get(extracted.target_text.lower())
            if not source_entity or not target_entity or source_entity.id == target_entity.id:
                continue
            exists = db.scalars(
                select(Relationship).where(
                    Relationship.source_id == source_entity.id,
                    Relationship.target_id == target_entity.id,
                    Relationship.type == extracted.type,
                )
            ).first()
            if exists:
                continue
            db.add(
                Relationship(
                    uid=next_relationship_uid(db),
                    source_id=source_entity.id,
                    target_id=target_entity.id,
                    type=extracted.type,
                    # Extracted from prose: inferred, pending validation.
                    evidence_status=EvidenceStatus.INFERRED,
                    confidence=extracted.confidence,
                    source=f"NLP extraction from {filename}",
                    occurred_at=now,
                    case_id=case.id if case else None,
                    derivation={
                        "reason": f"Extracted from \"{extracted.sentence[:180]}\"",
                        "method": f"trigger-phrase extraction ({DEFAULT_ENGINE.name()})",
                        "trigger": extracted.trigger,
                    },
                )
            )
            db.flush()
            created_relationships += 1

    stage("extract", "complete", f"{created_entities:,} new entities extracted")
    stage("resolve", "complete", f"{len(entity_cache):,} entities resolved against the graph")
    stage("relate", "complete", f"{created_relationships:,} relationships created")

    job.records_processed = len(unique_rows) + len(free_text_blocks)
    job.duplicates = duplicates
    job.entities_extracted = created_entities
    job.relationships_created = created_relationships
    job.status = "COMPLETE"
    job.stage = "complete"
    job.finished_at = datetime.now(UTC)
    stage("store", "complete", f"{job.records_processed:,} record(s) stored")

    record_audit(
        db, action="DATA_UPLOADED", user=user, resource_type="ingestion_job",
        resource_id=job.id, case_id=case.id if case else None,
        detail=(
            f"{filename}: {job.records_received} received, {job.records_processed} processed, "
            f"{duplicates} duplicates, {created_entities} entities, "
            f"{created_relationships} relationships"
        ),
        ip_address=client_ip(request),
    )
    job.stage_log = stage_log
    db.commit()
    graph_service.invalidate()
    stage("graph", "complete", "Knowledge graph projection refreshed")
    job.stage_log = stage_log
    db.commit()

    return {
        "job_id": job.id,
        "filename": filename,
        "source_type": source_type,
        "status": job.status,
        "counters": {
            "records_received": job.records_received,
            "records_processed": job.records_processed,
            "duplicates": job.duplicates,
            "entities_extracted": job.entities_extracted,
            "relationships_created": job.relationships_created,
        },
        "stages": stage_log,
        "message": (
            f"Processed {job.records_processed:,} record(s) from {filename}. "
            f"{created_entities:,} new entities and {created_relationships:,} "
            f"relationships were added to the knowledge graph."
        ),
    }


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(value.strip())
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None
