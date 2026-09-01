"""Projection of the relational store into the knowledge graph.

The database is the system of record. This service reads it and hands the
configured GraphRepository a consistent projection, then serves graph queries
from that projection.

Cache invalidation is explicit: any write path that changes entities or
relationships calls invalidate(). That is what keeps DESIGN.md's "one source
of truth" promise - there is no second copy of the data that can drift.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT / "graph") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "graph"))

from trinetra_graph.repository import (  # noqa: E402
    GraphEdge,
    GraphNode,
    GraphRepository,
    build_repository,
)

from app.config import settings  # noqa: E402
from app.db.base import EvidenceStatus  # noqa: E402
from app.db.models import Entity, Relationship  # noqa: E402

_lock = threading.RLock()
_repository: GraphRepository | None = None
_version = 0
_loaded_version = -1


def invalidate() -> None:
    """Mark the projection stale. Called by every graph-affecting write."""
    global _version
    with _lock:
        _version += 1


def graph_version() -> int:
    return _version


# ---------------------------------------------------------------- analytics

# Structural analytics are expensive and change only when the graph changes,
# so they are computed once per graph version and reused. Without this, one
# request recomputing betweenness over a few thousand nodes holds the GIL for
# a minute and starves every other request on the server.
_analytics_cache: dict[str, Any] = {"version": -1, "data": None}

# Betweenness and closeness are both O(V*E) exactly. Above this node count
# they are estimated from a seeded pivot sample instead, which keeps the whole
# analytics pass inside a few seconds rather than a minute.
EXACT_CENTRALITY_LIMIT = 700
CENTRALITY_PIVOTS = 220


def graph_analytics(db: Session) -> dict[str, Any]:
    """Centrality, communities and components for the current graph version.

    Returns a dict that also states whether betweenness is exact or estimated,
    so the UI can label it honestly rather than implying a precision the
    computation did not deliver.
    """
    repo = get_graph(db)
    with _lock:
        if _analytics_cache["version"] == _version and _analytics_cache["data"] is not None:
            return _analytics_cache["data"]

    snapshot = repo.snapshot()
    node_count = snapshot.node_count
    exact = node_count <= EXACT_CENTRALITY_LIMIT
    pivots = None if exact else CENTRALITY_PIVOTS

    from trinetra_graph import algorithms as algo

    adjacency = snapshot.adjacency
    betweenness = algo.betweenness_centrality(adjacency, pivots=pivots)
    closeness = algo.closeness_centrality(adjacency, pivots=pivots)
    communities, modularity = repo.communities()

    data = {
        "centrality": {
            "degree": algo.degree_centrality(adjacency),
            "degree_weighted": algo.degree_centrality(adjacency, weighted=True),
            "betweenness": betweenness,
            "closeness": closeness,
        },
        "communities": communities,
        "modularity": modularity,
        "components": repo.components(),
        "betweenness_exact": exact,
        "betweenness_pivots": pivots,
        "betweenness_note": (
            "Exact betweenness and closeness computed over the full graph."
            if exact
            else (
                f"Betweenness and closeness estimated from {CENTRALITY_PIVOTS} "
                f"sampled source nodes because the graph has {node_count:,} nodes. "
                f"Exact computation is O(V*E) and would block the server for a "
                f"minute. The estimate is deterministic for a given graph and is "
                f"suitable for ranking, but the absolute values are approximations. "
                f"Degree centrality and community detection remain exact."
            )
        ),
        "graph_version": _version,
    }

    with _lock:
        _analytics_cache["version"] = _version
        _analytics_cache["data"] = data
    return data


def _build_repository() -> GraphRepository:
    return build_repository(
        settings.GRAPH_BACKEND,
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
        database=settings.NEO4J_DATABASE,
    )


def get_graph(db: Session) -> GraphRepository:
    """Return the repository, rebuilding the projection if data has changed."""
    global _repository, _loaded_version
    with _lock:
        if _repository is None:
            _repository = _build_repository()
        if _loaded_version != _version:
            nodes, edges = _project(db)
            _repository.load(nodes, edges)
            _loaded_version = _version
        return _repository


def _project(db: Session) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Read active entities and relationships into graph form.

    Merged entities are excluded: after an accepted entity-resolution merge the
    absorbed record must stop appearing as a separate node.
    Rejected relationships are excluded: an investigator's rejection has to
    actually remove the edge from analysis, not merely relabel it.
    """
    entities = db.scalars(select(Entity).where(Entity.is_active.is_(True))).all()
    nodes = [
        GraphNode(
            uid=e.uid,
            type=e.type,
            name=e.name,
            attributes={
                "id": e.id,
                "classification": e.data_classification,
                "latitude": e.latitude,
                "longitude": e.longitude,
                **(e.attributes or {}),
            },
        )
        for e in entities
    ]
    active_uids = {e.uid for e in entities}
    id_to_uid = {e.id: e.uid for e in entities}

    relationships = db.scalars(
        select(Relationship).where(Relationship.evidence_status != EvidenceStatus.REJECTED)
    ).all()
    edges: list[GraphEdge] = []
    for r in relationships:
        source_uid = id_to_uid.get(r.source_id)
        target_uid = id_to_uid.get(r.target_id)
        if source_uid not in active_uids or target_uid not in active_uids:
            continue
        edges.append(
            GraphEdge(
                uid=r.uid,
                source=source_uid,
                target=target_uid,
                type=r.type,
                evidence_status=r.evidence_status,
                confidence=r.confidence,
                source_ref=r.source,
                time_label=r.time_label,
                attributes={"id": r.id, **(r.attributes or {})},
                derivation=r.derivation or {},
            )
        )
    return nodes, edges


# ---------------------------------------------------------------- helpers


def entity_by_uid(db: Session, uid: str) -> Entity | None:
    return db.scalars(select(Entity).where(Entity.uid == uid)).first()


def subgraph_payload(
    db: Session,
    uid: str,
    depth: int = 1,
    include_inferred: bool = True,
    types: list[str] | None = None,
) -> dict[str, Any]:
    """Neighbourhood around an entity, shaped for the graph canvas."""
    repo = get_graph(db)
    nodes, edges = repo.neighbourhood(uid, depth, include_inferred)
    if types:
        allowed = set(types)
        keep = {n.uid for n in nodes if n.type in allowed or n.uid == uid}
        nodes = [n for n in nodes if n.uid in keep]
        edges = [e for e in edges if e.source in keep and e.target in keep]
    return {
        "root": uid,
        "depth": depth,
        "include_inferred": include_inferred,
        "nodes": [_node_payload(n, root=uid) for n in nodes],
        "edges": [_edge_payload(e) for e in edges],
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "observed": sum(1 for e in edges if e.is_observed),
            "inferred": sum(1 for e in edges if not e.is_observed),
        },
        "backend": repo.backend_name(),
    }


def _node_payload(node: GraphNode, root: str | None = None) -> dict[str, Any]:
    return {
        "uid": node.uid,
        "type": node.type,
        "name": node.name,
        "is_root": node.uid == root,
        "classification": (node.attributes or {}).get("classification"),
        "latitude": (node.attributes or {}).get("latitude"),
        "longitude": (node.attributes or {}).get("longitude"),
    }


def _edge_payload(edge: GraphEdge) -> dict[str, Any]:
    return {
        "uid": edge.uid,
        "source": edge.source,
        "target": edge.target,
        "type": edge.type,
        "evidence_status": edge.evidence_status,
        "is_observed": edge.is_observed,
        "confidence": round(edge.confidence, 3),
        "source_ref": edge.source_ref,
        "time_label": edge.time_label,
        "has_derivation": bool(edge.derivation),
    }


def case_subgraph(db: Session, case_id: int, limit: int = 120) -> dict[str, Any]:
    """The graph for one case, capped so the canvas stays readable."""
    from app.db.models import CaseEntity

    entity_ids = db.scalars(
        select(CaseEntity.entity_id).where(CaseEntity.case_id == case_id)
    ).all()
    if not entity_ids:
        return {"nodes": [], "edges": [], "counts": {"nodes": 0, "edges": 0}}
    uids = db.scalars(
        select(Entity.uid).where(Entity.id.in_(entity_ids), Entity.is_active.is_(True))
    ).all()

    repo = get_graph(db)
    snapshot = repo.snapshot()
    selected = [u for u in uids if u in snapshot.nodes][:limit]
    selected_set = set(selected)
    nodes = [snapshot.nodes[u] for u in selected]
    edges = [
        e for e in snapshot.edges.values()
        if e.source in selected_set and e.target in selected_set
    ]
    return {
        "nodes": [_node_payload(n) for n in nodes],
        "edges": [_edge_payload(e) for e in edges],
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "observed": sum(1 for e in edges if e.is_observed),
            "inferred": sum(1 for e in edges if not e.is_observed),
        },
        "backend": repo.backend_name(),
    }
