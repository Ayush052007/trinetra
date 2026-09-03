"""Hidden-link discovery and entity resolution, wired to the database.

Both features share one rule: they propose, they never decide. Output is
always marked INFERRED, always carries the supporting record ids, and always
requires an authorised investigator to validate or reject before it changes
the case record.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

PROJECT_ROOT = Path(__file__).resolve().parents[3]
for _p in (PROJECT_ROOT / "ai", PROJECT_ROOT / "graph"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from trinetra_er.resolver import EntityResolver, ResolutionInput  # noqa: E402

from app.db.base import EvidenceStatus  # noqa: E402
from app.db.models import (  # noqa: E402
    CaseEntity,
    Entity,
    Relationship,
    ResolutionCandidate,
)
from app.services import graph_service  # noqa: E402

DISCOVERY_VERSION = "hiddenlink-1.0"


# ===================================================== hidden links


def discover_hidden_links(
    db: Session, case_id: int | None = None, limit: int = 25, min_confidence: float = 0.35
) -> list[dict[str, Any]]:
    """Find pairs with no direct edge but strong indirect evidence.

    Method: for every pair of entities two hops apart, score the connection on
    shared intermediaries (Adamic-Adar, which weights rare intermediaries above
    hubs), shared locations, and any financial path between them. Only pairs
    with no existing direct relationship are returned - an already-recorded
    link is not a discovery.
    """
    repo = graph_service.get_graph(db)
    snapshot = repo.snapshot()
    adjacency = snapshot.adjacency
    if not adjacency:
        return []

    entities = {
        e.uid: e
        for e in db.scalars(
            select(Entity)
            .where(Entity.is_active.is_(True))
            .options(selectinload(Entity.aliases))
        ).all()
    }

    scope: set[str] | None = None
    if case_id is not None:
        entity_ids = db.scalars(
            select(CaseEntity.entity_id).where(CaseEntity.case_id == case_id)
        ).all()
        scope = {
            e.uid for e in db.scalars(select(Entity).where(Entity.id.in_(entity_ids))).all()
        }

    # When no case is given, restrict the sweep to entities that actually
    # belong to a case. A full 2-hop sweep over every record in the background
    # corpus is quadratic, takes seconds, and returns pairs no investigation
    # asked about.
    if scope is None:
        case_entity_ids = db.scalars(select(CaseEntity.entity_id).distinct()).all()
        scope = {
            e.uid
            for e in db.scalars(
                select(Entity).where(Entity.id.in_(case_entity_ids))
            ).all()
        }

    # Only persons and organisations are interesting as endpoints; a pair of
    # phones sharing an owner is not a "hidden link", it is bookkeeping.
    def eligible(uid: str) -> bool:
        entity = entities.get(uid)
        if entity is None or entity.type not in ("person", "organization"):
            return False
        return scope is None or uid in scope

    seen: set[tuple[str, str]] = set()
    results: list[dict[str, Any]] = []

    # Hard ceiling on pairs examined. Discovery is a lead generator, not an
    # exhaustive proof, and an unbounded sweep would make the endpoint's cost
    # grow with the whole corpus rather than with the investigation.
    max_pairs = 20000
    examined = 0

    for uid in sorted(adjacency, key=str):
        if not eligible(uid):
            continue
        if examined >= max_pairs:
            break
        for intermediate in adjacency[uid]:
            for candidate in adjacency.get(intermediate, {}):
                if candidate == uid or not eligible(candidate):
                    continue
                if candidate in adjacency[uid]:
                    continue  # already directly connected
                key = tuple(sorted((uid, candidate)))
                if key in seen:
                    continue
                seen.add(key)
                examined += 1
                if examined >= max_pairs:
                    break

                shared = sorted(set(adjacency[uid]) & set(adjacency[candidate]))
                if not shared:
                    continue

                aa = repo.adamic_adar(uid, candidate) if hasattr(repo, "adamic_adar") else 0.0
                shared_locations = [
                    s for s in shared
                    if entities.get(s) and entities[s].type == "location"
                ]
                shared_people = [
                    s for s in shared
                    if entities.get(s) and entities[s].type == "person"
                ]
                shared_financial = [
                    s for s in shared
                    if entities.get(s) and entities[s].type in ("transaction", "organization")
                ]

                # Normalised blend. Adamic-Adar dominates because a rare shared
                # intermediary is far more telling than a common one.
                confidence = min(
                    0.92,
                    0.30 * min(1.0, aa / 2.0)
                    + 0.24 * min(1.0, len(shared_people) / 2.0)
                    + 0.18 * min(1.0, len(shared_financial) / 2.0)
                    + 0.12 * min(1.0, len(shared_locations) / 2.0)
                    + 0.16 * min(1.0, len(shared) / 4.0),
                )
                if confidence < min_confidence:
                    continue

                supporting_ids: list[int] = []
                for s in shared:
                    for edge in adjacency[uid].get(s, []):
                        rid = (edge.attributes or {}).get("id")
                        if rid:
                            supporting_ids.append(rid)
                    for edge in adjacency[candidate].get(s, []):
                        rid = (edge.attributes or {}).get("id")
                        if rid:
                            supporting_ids.append(rid)

                reasons = []
                if shared_people:
                    reasons.append(
                        f"{len(shared_people)} shared associate(s): "
                        + ", ".join(entities[s].name for s in shared_people[:3])
                    )
                if shared_financial:
                    reasons.append(
                        f"{len(shared_financial)} shared financial/organisational link(s): "
                        + ", ".join(entities[s].name for s in shared_financial[:3])
                    )
                if shared_locations:
                    reasons.append(
                        f"{len(shared_locations)} common location(s): "
                        + ", ".join(entities[s].name for s in shared_locations[:3])
                    )

                results.append({
                    "source_uid": uid,
                    "source_name": entities[uid].name,
                    "target_uid": candidate,
                    "target_name": entities[candidate].name,
                    "confidence": round(confidence, 3),
                    "evidence_status": EvidenceStatus.INFERRED,
                    "reason": "; ".join(reasons) or "Shared intermediaries",
                    "method": "common-neighbour analysis (Adamic-Adar weighted)",
                    "shared_entities": [
                        {"uid": s, "name": entities[s].name, "type": entities[s].type}
                        for s in shared[:8]
                    ],
                    "supporting_relationship_ids": sorted(set(supporting_ids))[:20],
                    "adamic_adar": round(aa, 4),
                    "requires_validation": True,
                    "algorithm_version": DISCOVERY_VERSION,
                    "disclaimer": (
                        "Inferred connection. Not an observed relationship and not "
                        "evidence of wrongdoing. Requires authorised investigator review."
                    ),
                })

    results.sort(key=lambda r: -r["confidence"])
    return results[:limit]


def path_between(db: Session, source_uid: str, target_uid: str, max_length: int = 4) -> dict[str, Any]:
    """Shortest path plus alternates, with the edges that make up each."""
    repo = graph_service.get_graph(db)
    snapshot = repo.snapshot()
    shortest = repo.path(source_uid, target_uid)
    alternates = repo.simple_paths(source_uid, target_uid, max_length=max_length, limit=6)

    def describe(path_nodes: list) -> dict[str, Any]:
        uids = [n.uid for n in path_nodes]
        hops = []
        for a, b in zip(uids, uids[1:]):
            edges = snapshot.adjacency.get(a, {}).get(b, [])
            best = max(edges, key=lambda e: e.confidence) if edges else None
            hops.append({
                "from": a,
                "to": b,
                "type": best.type if best else None,
                "evidence_status": best.evidence_status if best else None,
                "confidence": round(best.confidence, 3) if best else None,
                "source_ref": best.source_ref if best else None,
            })
        return {
            "nodes": [{"uid": n.uid, "name": n.name, "type": n.type} for n in path_nodes],
            "hops": hops,
            "length": len(uids) - 1,
            "all_observed": all(
                h["evidence_status"] in ("OBSERVED", "VALIDATED") for h in hops
            ) if hops else False,
        }

    return {
        "source": source_uid,
        "target": target_uid,
        "shortest": describe(shortest) if shortest else None,
        "alternates": [describe(p) for p in alternates if [n.uid for n in p] != [n.uid for n in shortest]],
        "found": bool(shortest),
    }


def common_connections(db: Session, uid_a: str, uid_b: str) -> list[dict[str, Any]]:
    repo = graph_service.get_graph(db)
    snapshot = repo.snapshot()
    shared = repo.common_connections(uid_a, uid_b)
    out = []
    for node in shared:
        edges_a = snapshot.adjacency.get(uid_a, {}).get(node.uid, [])
        edges_b = snapshot.adjacency.get(uid_b, {}).get(node.uid, [])
        out.append({
            "uid": node.uid,
            "name": node.name,
            "type": node.type,
            "via_a": [{"type": e.type, "source_ref": e.source_ref} for e in edges_a],
            "via_b": [{"type": e.type, "source_ref": e.source_ref} for e in edges_b],
        })
    return out


# ================================================== entity resolution


def _resolution_inputs(db: Session, scope_uids: set[str] | None = None) -> list[ResolutionInput]:
    repo = graph_service.get_graph(db)
    snapshot = repo.snapshot()
    entities = db.scalars(
        select(Entity).where(Entity.is_active.is_(True), Entity.type == "person")
    ).all()

    id_to_uid = {e.id: e.uid for e in entities}
    case_map: dict[str, set[str]] = {}
    for entity_id, case_id in db.execute(
        select(CaseEntity.entity_id, CaseEntity.case_id)
    ).all():
        uid = id_to_uid.get(entity_id)
        if uid:
            case_map.setdefault(uid, set()).add(str(case_id))

    out: list[ResolutionInput] = []
    for entity in entities:
        if scope_uids is not None and entity.uid not in scope_uids:
            continue
        attributes = dict(entity.attributes or {})
        # Fold connected phone/vehicle identifiers into the comparable
        # attributes, since that is how alias links surface in practice.
        for neighbour_uid in snapshot.adjacency.get(entity.uid, {}):
            neighbour = snapshot.nodes.get(neighbour_uid)
            if neighbour is None:
                continue
            if neighbour.type == "phone":
                attributes.setdefault("phone", neighbour.name)
            elif neighbour.type == "vehicle":
                attributes.setdefault("vehicle", neighbour.name.replace(" ", "").replace("-", ""))
        out.append(
            ResolutionInput(
                uid=entity.uid,
                type=entity.type,
                name=entity.name,
                aliases=[a.alias for a in entity.aliases],
                attributes=attributes,
                neighbour_uids=set(snapshot.adjacency.get(entity.uid, {})),
                case_uids=case_map.get(entity.uid, set()),
            )
        )
    return out


def refresh_resolution_candidates(db: Session, limit: int = 60) -> int:
    """Recompute pending candidates. Decided pairs are never re-proposed."""
    resolver = EntityResolver()
    inputs = _resolution_inputs(db)
    candidates = resolver.find_candidates(inputs)

    entities = {
        e.uid: e
        for e in db.scalars(
            select(Entity)
            .where(Entity.is_active.is_(True))
            .options(selectinload(Entity.aliases))
        ).all()
    }
    decided: set[tuple[int, int]] = {
        tuple(sorted((row.entity_a_id, row.entity_b_id)))
        for row in db.scalars(
            select(ResolutionCandidate).where(ResolutionCandidate.status != "PENDING")
        ).all()
    }
    existing_pending = {
        tuple(sorted((row.entity_a_id, row.entity_b_id))): row
        for row in db.scalars(
            select(ResolutionCandidate).where(ResolutionCandidate.status == "PENDING")
        ).all()
    }

    created = 0
    for candidate in candidates[:limit]:
        a = entities.get(candidate.uid_a)
        b = entities.get(candidate.uid_b)
        if not a or not b:
            continue
        key = tuple(sorted((a.id, b.id)))
        if key in decided:
            continue
        factors = [f.to_dict() for f in candidate.factors]
        if key in existing_pending:
            row = existing_pending[key]
            row.confidence = candidate.confidence
            row.factors = factors
            continue
        db.add(
            ResolutionCandidate(
                entity_a_id=key[0],
                entity_b_id=key[1],
                confidence=candidate.confidence,
                factors=factors,
                status="PENDING",
                algorithm_version=EntityResolver.VERSION,
            )
        )
        created += 1
    db.flush()
    return created


def candidate_payload(row: ResolutionCandidate, a: Entity, b: Entity) -> dict[str, Any]:
    return {
        "id": row.id,
        "status": row.status,
        "confidence": round(row.confidence, 3),
        "entity_a": {"uid": a.uid, "name": a.name, "type": a.type,
                     "aliases": [x.alias for x in a.aliases]},
        "entity_b": {"uid": b.uid, "name": b.name, "type": b.type,
                     "aliases": [x.alias for x in b.aliases]},
        "matching_factors": sorted(row.factors, key=lambda f: -f.get("contribution", 0)),
        "review_required": row.status == "PENDING",
        "algorithm_version": row.algorithm_version,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "disclaimer": (
            "Potential match proposed by entity resolution. Records are never "
            "merged automatically - an authorised investigator must accept or reject."
        ),
    }


def apply_merge(db: Session, candidate: ResolutionCandidate, user_id: int) -> Relationship:
    """Accept a match: link the records with an alias_of edge and deactivate one.

    The absorbed entity is deactivated rather than deleted, and merged_into_id
    records where it went, so the decision is fully reversible and the original
    record remains available for audit.
    """
    survivor = db.get(Entity, candidate.entity_a_id)
    absorbed = db.get(Entity, candidate.entity_b_id)
    # Keep whichever record carries more information as the survivor.
    if len(absorbed.name) > len(survivor.name):
        survivor, absorbed = absorbed, survivor

    absorbed.is_active = False
    absorbed.merged_into_id = survivor.id

    from app.services.mutations import next_relationship_uid

    edge = Relationship(
        uid=next_relationship_uid(db),
        source_id=survivor.id,
        target_id=absorbed.id,
        type="alias_of",
        evidence_status=EvidenceStatus.VALIDATED,
        confidence=candidate.confidence,
        source="Entity resolution (investigator confirmed)",
        occurred_at=datetime.now(UTC),
        derivation={
            "reason": "Accepted entity-resolution match",
            "method": candidate.algorithm_version,
            "factors": candidate.factors,
        },
        validated_by_id=user_id,
        validated_at=datetime.now(UTC),
    )
    db.add(edge)

    # Carry the absorbed record's aliases across so search still finds it.
    from app.db.models import EntityAlias
    from trinetra_nlp.engine import normalize

    existing = {a.normalized_alias for a in survivor.aliases}
    for surface in [absorbed.name, *[a.alias for a in absorbed.aliases]]:
        key = normalize(surface, survivor.type)
        if key and key not in existing:
            db.add(
                EntityAlias(
                    entity_id=survivor.id, alias=surface, normalized_alias=key,
                    source="Merged from entity resolution",
                )
            )
            existing.add(key)

    db.flush()
    graph_service.invalidate()
    return edge
