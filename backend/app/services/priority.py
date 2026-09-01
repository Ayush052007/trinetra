"""Investigation Priority Score.

WHAT THIS IS: an analytical triage signal that ranks which entities warrant an
investigator's attention first, computed from structural and behavioural
properties of the recorded data.

WHAT THIS IS NOT: a probability of guilt, criminality, or involvement in an
offence. A high score means "this record sits at a busy junction of the
available data", which is a statement about the data, not about the person.
Every consumer of this module must preserve that distinction.

Each factor is computed from stored records, carries its own weight and
contribution, and cites the evidence behind it. Nothing is opaque.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import EvidenceStatus
from app.db.models import Case, CaseEntity, Entity, PriorityScore, Relationship
from app.services import graph_service

ALGORITHM_VERSION = "ips-1.0"

# Weights sum to 1.0. Published in the UI alongside every score.
WEIGHTS = {
    "connectivity": 0.24,
    "brokerage": 0.20,
    "interaction_frequency": 0.16,
    "financial": 0.14,
    "case_association": 0.12,
    "temporal": 0.08,
    "location": 0.06,
}

FACTOR_LABELS = {
    "connectivity": "Network connectivity",
    "brokerage": "Brokerage position",
    "interaction_frequency": "Relationship frequency",
    "financial": "Transaction patterns",
    "case_association": "Case associations",
    "temporal": "Temporal activity pattern",
    "location": "Location associations",
}

FACTOR_DESCRIPTIONS = {
    "connectivity": "How many distinct entities this record is directly connected to, relative to the rest of the dataset.",
    "brokerage": "How often this record lies on the shortest path between two otherwise unconnected entities.",
    "interaction_frequency": "Volume of recorded interactions such as calls and meetings.",
    "financial": "Number and magnitude of associated financial records.",
    "case_association": "How many open cases this record appears in.",
    "temporal": "Whether recorded activity is escalating, steady, or historical.",
    "location": "Number of distinct locations this record is associated with.",
}


def _band(score: float) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def _percentile_ranker(values: dict[str, float]):
    """Return f(uid) -> 0..1 percentile rank within the population.

    Percentile rather than raw value: a degree of 14 means nothing on its own,
    but "higher than 96% of records in this dataset" is interpretable and
    stays meaningful as the dataset grows.
    """
    ordered = sorted(values.values())
    n = len(ordered)
    if n == 0:
        return lambda uid: 0.0

    def rank(uid: str) -> float:
        value = values.get(uid, 0.0)
        low, high = 0, n
        while low < high:
            mid = (low + high) // 2
            if ordered[mid] < value:
                low = mid + 1
            else:
                high = mid
        return low / n if n else 0.0

    return rank


def compute_scores(
    db: Session, case_id: int | None = None, limit: int | None = None
) -> list[PriorityScore]:
    """Recompute and persist priority scores. Returns the stored rows."""
    repo = graph_service.get_graph(db)
    snapshot = repo.snapshot()
    if not snapshot.nodes:
        return []

    centrality = graph_service.graph_analytics(db)["centrality"]
    degree = centrality["degree"]
    degree_weighted = centrality["degree_weighted"]
    betweenness = centrality["betweenness"]

    degree_rank = _percentile_ranker(degree)
    weighted_rank = _percentile_ranker(degree_weighted)
    between_rank = _percentile_ranker(betweenness)

    entities = db.scalars(select(Entity).where(Entity.is_active.is_(True))).all()
    by_uid = {e.uid: e for e in entities}

    # Precompute per-entity aggregates in one pass over relationships.
    relationships = db.scalars(
        select(Relationship).where(Relationship.evidence_status != EvidenceStatus.REJECTED)
    ).all()
    id_to_uid = {e.id: e.uid for e in entities}

    interactions: dict[str, int] = {}
    financial_count: dict[str, int] = {}
    financial_value: dict[str, float] = {}
    locations: dict[str, set[str]] = {}
    timestamps: dict[str, list[datetime]] = {}
    evidence_refs: dict[str, set[str]] = {}

    for r in relationships:
        su, tu = id_to_uid.get(r.source_id), id_to_uid.get(r.target_id)
        for uid in (su, tu):
            if uid is None:
                continue
            if r.type in ("CALLED", "MET", "sent_messages_to"):
                count = (r.attributes or {}).get("call_count", 1)
                interactions[uid] = interactions.get(uid, 0) + int(count or 1)
            if r.type == "TRANSFERRED_MONEY":
                financial_count[uid] = financial_count.get(uid, 0) + 1
                amount = (r.attributes or {}).get("amount")
                if amount:
                    financial_value[uid] = financial_value.get(uid, 0.0) + float(amount)
            if r.occurred_at:
                timestamps.setdefault(uid, []).append(r.occurred_at)
            if r.source:
                evidence_refs.setdefault(uid, set()).add(r.source)
        # Location association is directional in meaning but not in storage.
        if su and tu:
            if by_uid.get(tu) and by_uid[tu].type == "location":
                locations.setdefault(su, set()).add(tu)
            if by_uid.get(su) and by_uid[su].type == "location":
                locations.setdefault(tu, set()).add(su)

    case_counts: dict[str, int] = {}
    open_case_ids = {
        c.id for c in db.scalars(select(Case).where(Case.status != "CLOSED")).all()
    }
    for entity_id, linked_case in db.execute(
        select(CaseEntity.entity_id, CaseEntity.case_id)
    ).all():
        uid = id_to_uid.get(entity_id)
        if uid and linked_case in open_case_ids:
            case_counts[uid] = case_counts.get(uid, 0) + 1

    interaction_rank = _percentile_ranker(
        {uid: float(v) for uid, v in interactions.items()}
    )
    financial_rank = _percentile_ranker(
        {uid: float(v) for uid, v in financial_value.items()}
    )

    now = datetime.now(UTC)
    recent_window = now - timedelta(days=45)

    # Restrict to the requested case if one was given.
    target_uids: list[str]
    if case_id is not None:
        entity_ids = db.scalars(
            select(CaseEntity.entity_id).where(CaseEntity.case_id == case_id)
        ).all()
        target_uids = [id_to_uid[i] for i in entity_ids if i in id_to_uid]
    else:
        target_uids = list(by_uid)

    db.execute(
        PriorityScore.__table__.delete().where(
            PriorityScore.entity_id.in_([by_uid[u].id for u in target_uids if u in by_uid])
        )
        if target_uids
        else PriorityScore.__table__.delete()
    )

    rows: list[PriorityScore] = []
    for uid in target_uids:
        entity = by_uid.get(uid)
        if entity is None:
            continue

        factors: list[dict[str, Any]] = []

        def add(key: str, value: float, detail: str, evidence: list[str] | None = None):
            factors.append({
                "key": key,
                "label": FACTOR_LABELS[key],
                "description": FACTOR_DESCRIPTIONS[key],
                "value": round(value, 4),
                "weight": WEIGHTS[key],
                "contribution": round(WEIGHTS[key] * value * 100, 2),
                "detail": detail,
                "evidence": evidence or [],
            })

        connections = len(snapshot.adjacency.get(uid, {}))
        add(
            "connectivity", degree_rank(uid),
            f"{connections} direct connection(s) - higher than "
            f"{degree_rank(uid) * 100:.0f}% of records in the dataset",
        )
        add(
            "brokerage", between_rank(uid),
            f"Betweenness above {between_rank(uid) * 100:.0f}% of records"
            + (" - sits between otherwise unconnected groups" if between_rank(uid) > 0.9 else ""),
        )
        interaction_total = interactions.get(uid, 0)
        add(
            "interaction_frequency",
            max(interaction_rank(uid), weighted_rank(uid) * 0.5),
            f"{interaction_total} recorded interaction(s) across calls, meetings and messages",
            sorted(evidence_refs.get(uid, set()))[:5],
        )
        value = financial_value.get(uid, 0.0)
        add(
            "financial", financial_rank(uid) if value else 0.0,
            f"{financial_count.get(uid, 0)} financial record(s)"
            + (f" totalling Rs {value:,.0f}" if value else " - none recorded"),
        )
        cases = case_counts.get(uid, 0)
        add(
            "case_association", min(1.0, cases / 2.0),
            f"Appears in {cases} open case(s)",
        )

        stamps = sorted(timestamps.get(uid, []))
        if len(stamps) >= 2:
            recent = sum(1 for s in stamps if s >= recent_window)
            share = recent / len(stamps)
            temporal_detail = (
                f"{recent} of {len(stamps)} recorded events fall in the last 45 days"
            )
            if share > 0.5:
                temporal_detail += " - activity is concentrated recently"
            temporal_value = share
        elif stamps:
            temporal_value = 0.2
            temporal_detail = "Single dated record - no trend can be established"
        else:
            temporal_value = 0.0
            temporal_detail = "No dated records"
        add("temporal", temporal_value, temporal_detail)

        distinct_locations = len(locations.get(uid, set()))
        add(
            "location", min(1.0, distinct_locations / 4.0),
            f"Associated with {distinct_locations} distinct location(s)",
        )

        score = round(sum(f["contribution"] for f in factors), 2)
        # Confidence reflects how much evidence the score rests on, not how
        # certain we are that the entity is of interest.
        supporting = connections + interaction_total + financial_count.get(uid, 0)
        confidence = round(min(0.95, 0.35 + 0.05 * min(supporting, 12)), 3)

        rows.append(
            PriorityScore(
                entity_id=entity.id,
                case_id=case_id,
                score=score,
                band=_band(score),
                confidence=confidence,
                factors=factors,
                algorithm_version=ALGORITHM_VERSION,
                computed_at=now,
            )
        )

    rows.sort(key=lambda r: -r.score)
    if limit:
        rows = rows[:limit]
    db.add_all(rows)
    db.flush()
    return rows


def score_payload(row: PriorityScore, entity: Entity) -> dict[str, Any]:
    return {
        "entity_uid": entity.uid,
        "entity_name": entity.name,
        "entity_type": entity.type,
        "score": round(row.score, 1),
        "band": row.band,
        "confidence": row.confidence,
        "factors": sorted(row.factors, key=lambda f: -f["contribution"]),
        "algorithm_version": row.algorithm_version,
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        "disclaimer": (
            "Investigation Priority Score is an analytical triage signal derived "
            "from recorded data. It is not a probability of guilt, criminality or "
            "involvement in any offence, and must not be used as evidence."
        ),
    }
