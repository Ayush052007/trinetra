"""AI / NLP analysis endpoint."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import api_rate_limiter, client_ip, require_permission
from app.core.rbac import Perm
from app.db.base import DataClassification, EvidenceStatus
from app.db.models import Case, CaseEntity, Entity, EntityAlias, Relationship, User
from app.db.session import get_db
from app.services import graph_service
from app.services.mutations import next_relationship_uid, record_audit

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "ai"))
if str(PROJECT_ROOT / "database") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "database"))

from trinetra_nlp.engine import DEFAULT_ENGINE, Gazetteer, normalize  # noqa: E402

import seed_data as SD  # noqa: E402

router = APIRouter(prefix="/nlp", tags=["nlp"], dependencies=[Depends(api_rate_limiter)])

MAX_TEXT_LENGTH = 20000


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    case_id: int | None = None


class CommitRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    case_id: int | None = None
    accept_entities: list[str] = Field(default_factory=list, description="Entity surface forms to persist")
    accept_relationships: list[int] = Field(default_factory=list, description="Indices of relationships to persist")


def build_gazetteer(db: Session, limit: int = 6000) -> Gazetteer:
    """Build the recognition dictionary from the live knowledge graph.

    Extraction therefore improves as the graph grows: an entity named in one
    report is recognised by name in the next.
    """
    gazetteer = Gazetteer()
    rows = db.scalars(
        select(Entity).where(Entity.is_active.is_(True)).limit(limit)
    ).all()
    aliases: dict[int, list[str]] = {}
    for alias in db.scalars(select(EntityAlias)).all():
        aliases.setdefault(alias.entity_id, []).append(alias.alias)
    for entity in rows:
        gazetteer.add(entity.uid, entity.type, entity.name, aliases.get(entity.id, []))
    return gazetteer


@router.get("/sample")
def sample_texts(user: User = Depends(require_permission(Perm.NLP_RUN))) -> dict[str, Any]:
    """Sample source documents, taken from the project material."""
    return {
        "samples": [
            {
                "key": "fir",
                "label": "FIR extract - Financial Network (NX-2026-0147)",
                "text": SD.SAMPLE_FIR_TEXT,
            },
            {
                "key": "ws",
                "label": "Case narrative - Women Safety (DEMO/WS-2026-0417)",
                "text": SD.SAMPLE_WS_TEXT,
            },
        ]
    }


@router.post("/analyze")
def analyze(
    payload: AnalyzeRequest,
    request: Request,
    user: User = Depends(require_permission(Perm.NLP_RUN)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Extract entities and relationships from unstructured text.

    Nothing is written to the graph here - this is analysis only. The response
    carries character spans so the client can highlight exactly which text
    produced each extraction.
    """
    gazetteer = build_gazetteer(db)
    result = DEFAULT_ENGINE.analyze(payload.text, gazetteer)
    output = result.to_dict()

    # Mark which extracted entities already exist, so the client can show
    # "will link" versus "will create".
    for entity in output["entities"]:
        entity["exists"] = bool(entity.get("entity_uid"))
        entity["action"] = "link" if entity["exists"] else "create"

    for index, relationship in enumerate(output["relationships"]):
        relationship["index"] = index
        relationship["evidence_status"] = EvidenceStatus.INFERRED
        relationship["requires_validation"] = True

    record_audit(
        db, action="NLP_ANALYSIS", user=user, resource_type="nlp",
        case_id=payload.case_id,
        detail=(
            f"{len(output['entities'])} entities, "
            f"{len(output['relationships'])} relationships from "
            f"{len(payload.text)} characters"
        ),
        ip_address=client_ip(request),
    )
    db.commit()

    output["pipeline"] = [
        {"stage": "tokenise", "label": "Sentence segmentation", "status": "complete"},
        {"stage": "ner", "label": "Named entity recognition", "status": "complete",
         "detail": f"{sum(1 for e in output['entities'] if e['method'] == 'pattern')} pattern matches"},
        {"stage": "gazetteer", "label": "Knowledge-graph lookup", "status": "complete",
         "detail": f"{sum(1 for e in output['entities'] if e['method'] == 'gazetteer')} known entities"},
        {"stage": "classify", "label": "Entity classification", "status": "complete"},
        {"stage": "normalise", "label": "Normalisation", "status": "complete"},
        {"stage": "relations", "label": "Relationship extraction", "status": "complete",
         "detail": f"{len(output['relationships'])} candidate relationships"},
        {"stage": "confidence", "label": "Confidence scoring", "status": "complete",
         "detail": f"overall {output['confidence']:.2f}"},
    ]
    output["engine_note"] = (
        "Deterministic rule-based extraction: regular-expression recognisers for "
        "structured identifiers, dictionary matching against the knowledge graph, "
        "and trigger-phrase relationship extraction. Every result carries the "
        "character span it was derived from. No statistical model is bundled; the "
        "NlpEngine interface allows one to be substituted where available."
    )
    output["disclaimer"] = (
        "Extracted relationships are candidates, not established facts. They enter "
        "the knowledge graph as INFERRED and require investigator validation."
    )
    return output


@router.post("/commit")
def commit_to_graph(
    payload: CommitRequest,
    request: Request,
    user: User = Depends(require_permission(Perm.NLP_RUN, Perm.RELATIONSHIP_CREATE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Persist selected extractions into the knowledge graph.

    New entities are created; recognised ones are linked rather than
    duplicated. Extracted relationships are stored as INFERRED so they appear
    in the validation queue rather than silently becoming case fact.
    """
    gazetteer = build_gazetteer(db)
    result = DEFAULT_ENGINE.analyze(payload.text, gazetteer)

    case = db.get(Case, payload.case_id) if payload.case_id else None
    accepted = {s.lower() for s in payload.accept_entities}
    now = datetime.now(UTC)

    created_entities: list[dict] = []
    linked_entities: list[dict] = []
    uid_by_surface: dict[str, str] = {}

    max_uid = db.scalar(select(Entity.uid).order_by(Entity.id.desc())) or ""
    counter = db.scalar(select(Entity.id).order_by(Entity.id.desc())) or 0

    for extracted in result.entities:
        # Dates/day labels are timeline anchors, not entities in their own right.
        if extracted.type == "event":
            continue
        if accepted and extracted.text.lower() not in accepted:
            continue

        if extracted.entity_uid:
            entity = db.scalars(
                select(Entity).where(Entity.uid == extracted.entity_uid)
            ).first()
            if entity:
                uid_by_surface[extracted.text.lower()] = entity.uid
                linked_entities.append({"uid": entity.uid, "name": entity.name, "type": entity.type})
                if case and not db.scalars(
                    select(CaseEntity).where(
                        CaseEntity.case_id == case.id, CaseEntity.entity_id == entity.id
                    )
                ).first():
                    db.add(
                        CaseEntity(
                            case_id=case.id, entity_id=entity.id,
                            added_at=now, added_by_id=user.id,
                        )
                    )
                continue

        # Guard against creating a duplicate of something already stored.
        normalized = normalize(extracted.text, extracted.type)
        existing = db.scalars(
            select(Entity).where(
                Entity.normalized_name == normalized,
                Entity.type == extracted.type,
                Entity.is_active.is_(True),
            )
        ).first()
        if existing:
            uid_by_surface[extracted.text.lower()] = existing.uid
            linked_entities.append({"uid": existing.uid, "name": existing.name, "type": existing.type})
            continue

        counter += 1
        uid = f"nlp-{counter:06d}"
        entity = Entity(
            uid=uid,
            type=extracted.type,
            name=extracted.text,
            normalized_name=normalized,
            attributes={
                "extracted_by": DEFAULT_ENGINE.name(),
                "extraction_method": extracted.method,
                "extraction_confidence": extracted.confidence,
            },
            source=f"NLP extraction by {user.service_id}",
            data_classification=DataClassification.SYNTHETIC,
        )
        db.add(entity)
        db.flush()
        uid_by_surface[extracted.text.lower()] = uid
        created_entities.append({"uid": uid, "name": entity.name, "type": entity.type})
        if case:
            db.add(
                CaseEntity(
                    case_id=case.id, entity_id=entity.id, added_at=now, added_by_id=user.id
                )
            )

    # Relationships.
    wanted = set(payload.accept_relationships) if payload.accept_relationships else None
    created_relationships: list[dict] = []
    for index, extracted in enumerate(result.relationships):
        if wanted is not None and index not in wanted:
            continue
        source_uid = extracted.source_uid or uid_by_surface.get(extracted.source_text.lower())
        target_uid = extracted.target_uid or uid_by_surface.get(extracted.target_text.lower())
        if not source_uid or not target_uid or source_uid == target_uid:
            continue
        source = db.scalars(select(Entity).where(Entity.uid == source_uid)).first()
        target = db.scalars(select(Entity).where(Entity.uid == target_uid)).first()
        if not source or not target:
            continue

        duplicate = db.scalars(
            select(Relationship).where(
                Relationship.source_id == source.id,
                Relationship.target_id == target.id,
                Relationship.type == extracted.type,
            )
        ).first()
        if duplicate:
            continue

        rel = Relationship(
            uid=next_relationship_uid(db),
            source_id=source.id,
            target_id=target.id,
            type=extracted.type,
            evidence_status=EvidenceStatus.INFERRED,
            confidence=extracted.confidence,
            source=f"NLP extraction ({DEFAULT_ENGINE.name()})",
            occurred_at=now,
            case_id=case.id if case else None,
            derivation={
                "reason": (
                    f"Extracted from the phrase \"{extracted.trigger}\" in: "
                    f"\"{extracted.sentence[:200]}\""
                ),
                "method": f"trigger-phrase extraction ({DEFAULT_ENGINE.name()})",
                "trigger": extracted.trigger,
                "sentence": extracted.sentence,
                "character_span": [extracted.trigger_start, extracted.trigger_end],
                "supporting_relationship_ids": [],
            },
        )
        db.add(rel)
        db.flush()
        created_relationships.append({
            "relationship_id": rel.id,
            "source": source.name,
            "target": target.name,
            "type": rel.type,
            "confidence": round(rel.confidence, 3),
            "evidence_status": rel.evidence_status,
        })

    record_audit(
        db, action="NLP_COMMIT", user=user, resource_type="nlp",
        case_id=case.id if case else None,
        detail=(
            f"{len(created_entities)} entities created, {len(linked_entities)} linked, "
            f"{len(created_relationships)} relationships added as INFERRED"
        ),
        ip_address=client_ip(request),
    )
    db.commit()
    graph_service.invalidate()

    return {
        "created_entities": created_entities,
        "linked_entities": linked_entities,
        "created_relationships": created_relationships,
        "counts": {
            "created": len(created_entities),
            "linked": len(linked_entities),
            "relationships": len(created_relationships),
        },
        "message": (
            f"Added {len(created_entities)} new and linked {len(linked_entities)} existing "
            f"entities. {len(created_relationships)} relationship(s) stored as INFERRED "
            f"and queued for validation."
        ),
    }
