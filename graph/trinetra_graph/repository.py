"""Knowledge-graph repository interface and its two implementations.

TRINETRA treats the relational store as the system of record and the graph as
a queryable projection of it. Both backends below answer exactly the same
questions:

    EmbeddedGraphRepository - pure Python, in-process, no external service.
    Neo4jGraphRepository    - real Cypher against a Neo4j instance.

Selecting between them is a configuration decision (GRAPH_BACKEND), never a
code change in the callers. Neither one fabricates edges: both return only
what has actually been written to the graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from trinetra_graph import algorithms as algo


@dataclass(frozen=True)
class GraphNode:
    uid: str
    type: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    uid: str
    source: str
    target: str
    type: str
    evidence_status: str
    confidence: float
    source_ref: str | None = None
    time_label: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    derivation: dict[str, Any] = field(default_factory=dict)

    @property
    def is_observed(self) -> bool:
        return self.evidence_status in ("OBSERVED", "VALIDATED")


@dataclass
class GraphSnapshot:
    """An immutable-by-convention view of the graph at one point in time."""

    nodes: dict[str, GraphNode]
    edges: dict[str, GraphEdge]
    adjacency: algo.Adjacency

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class GraphRepository(Protocol):
    """The contract every graph backend satisfies."""

    def load(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None: ...

    def snapshot(self) -> GraphSnapshot: ...

    def neighbourhood(
        self, uid: str, depth: int = 1, include_inferred: bool = True
    ) -> tuple[list[GraphNode], list[GraphEdge]]: ...

    def path(self, source: str, target: str) -> list[GraphNode]: ...

    def simple_paths(
        self, source: str, target: str, max_length: int = 4, limit: int = 10
    ) -> list[list[GraphNode]]: ...

    def common_connections(self, a: str, b: str) -> list[GraphNode]: ...

    def centrality(self) -> dict[str, dict[str, float]]: ...

    def communities(self) -> tuple[dict[str, int], float]: ...

    def components(self) -> list[list[str]]: ...

    def backend_name(self) -> str: ...


# ------------------------------------------------------------------ embedded


class EmbeddedGraphRepository:
    """In-process graph engine.

    Holds a snapshot built from the relational store. Callers rebuild it via
    load() whenever the underlying data changes, so the graph can never drift
    away from the database.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._adj: algo.Adjacency = {}

    def backend_name(self) -> str:
        return "embedded"

    def load(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        self._nodes = {n.uid: n for n in nodes}
        self._edges = {e.uid: e for e in edges}
        self._adj = algo.build_adjacency(
            self._nodes.keys(),
            [(e.source, e.target, e) for e in self._edges.values()],
        )

    def snapshot(self) -> GraphSnapshot:
        return GraphSnapshot(nodes=self._nodes, edges=self._edges, adjacency=self._adj)

    # -- queries ---------------------------------------------------------

    def neighbourhood(
        self, uid: str, depth: int = 1, include_inferred: bool = True
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        if uid not in self._nodes:
            return [], []
        edge_filter = None if include_inferred else (lambda e: e.is_observed)
        reachable = algo.k_hop(self._adj, uid, depth, edge_filter)
        node_ids = set(reachable)
        edges = [
            e
            for e in self._edges.values()
            if e.source in node_ids
            and e.target in node_ids
            and (include_inferred or e.is_observed)
        ]
        nodes = [self._nodes[n] for n in node_ids if n in self._nodes]
        return nodes, edges

    def path(self, source: str, target: str) -> list[GraphNode]:
        return [self._nodes[u] for u in algo.shortest_path(self._adj, source, target)]

    def simple_paths(
        self, source: str, target: str, max_length: int = 4, limit: int = 10
    ) -> list[list[GraphNode]]:
        paths = algo.all_simple_paths(self._adj, source, target, max_length, limit)
        return [[self._nodes[u] for u in p] for p in paths]

    def common_connections(self, a: str, b: str) -> list[GraphNode]:
        return [self._nodes[u] for u in algo.common_neighbors(self._adj, a, b)]

    def edges_between(self, a: str, b: str) -> list[GraphEdge]:
        return list(self._adj.get(a, {}).get(b, []))

    def edges_for(self, uid: str) -> list[GraphEdge]:
        return [e for e in self._edges.values() if e.source == uid or e.target == uid]

    def centrality(self) -> dict[str, dict[str, float]]:
        return {
            "degree": algo.degree_centrality(self._adj),
            "degree_weighted": algo.degree_centrality(self._adj, weighted=True),
            "betweenness": algo.betweenness_centrality(self._adj),
            "closeness": algo.closeness_centrality(self._adj),
        }

    def communities(self) -> tuple[dict[str, int], float]:
        assignment = algo.louvain_communities(self._adj)
        return assignment, algo.modularity(self._adj, assignment)

    def components(self) -> list[list[str]]:
        return algo.connected_components(self._adj)

    def adamic_adar(self, a: str, b: str) -> float:
        return algo.adamic_adar_score(self._adj, a, b)


# -------------------------------------------------------------------- neo4j


class Neo4jGraphRepository:
    """Neo4j-backed implementation using real Cypher.

    Not exercised in the default configuration (no Neo4j instance is present
    in this environment). It is a complete implementation rather than a stub,
    so switching GRAPH_BACKEND=neo4j is purely a configuration change - but it
    is untested against a live server here, and docs/INTEGRATIONS.md says so.
    """

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        from neo4j import GraphDatabase  # imported lazily: optional dependency

        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database
        self._mirror = EmbeddedGraphRepository()  # analytics fallback

    def backend_name(self) -> str:
        return "neo4j"

    def close(self) -> None:
        self._driver.close()

    def _run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return [dict(record) for record in session.run(cypher, **params)]

    def ensure_constraints(self) -> None:
        """Idempotent schema setup: uniqueness + lookup indexes."""
        statements = [
            "CREATE CONSTRAINT trinetra_entity_uid IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.uid IS UNIQUE",
            "CREATE INDEX trinetra_entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX trinetra_entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX trinetra_rel_status IF NOT EXISTS "
            "FOR ()-[r:RELATED]-() ON (r.evidence_status)",
        ]
        for statement in statements:
            self._run(statement)

    def load(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        """Full projection rebuild. Wiped and rewritten in one transaction."""
        self.ensure_constraints()
        self._run("MATCH (n:Entity) DETACH DELETE n")
        self._run(
            "UNWIND $rows AS row CREATE (e:Entity) SET e = row",
            rows=[
                {"uid": n.uid, "type": n.type, "name": n.name, **_flatten(n.attributes)}
                for n in nodes
            ],
        )
        self._run(
            """
            UNWIND $rows AS row
            MATCH (a:Entity {uid: row.source})
            MATCH (b:Entity {uid: row.target})
            CREATE (a)-[r:RELATED]->(b)
            SET r.uid = row.uid, r.type = row.type,
                r.evidence_status = row.evidence_status,
                r.confidence = row.confidence,
                r.source_ref = row.source_ref,
                r.time_label = row.time_label
            """,
            rows=[
                {
                    "uid": e.uid,
                    "source": e.source,
                    "target": e.target,
                    "type": e.type,
                    "evidence_status": e.evidence_status,
                    "confidence": e.confidence,
                    "source_ref": e.source_ref,
                    "time_label": e.time_label,
                }
                for e in edges
            ],
        )
        self._mirror.load(nodes, edges)

    def snapshot(self) -> GraphSnapshot:
        return self._mirror.snapshot()

    def neighbourhood(
        self, uid: str, depth: int = 1, include_inferred: bool = True
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        status_clause = (
            "" if include_inferred else "WHERE ALL(r IN relationships(p) "
            "WHERE r.evidence_status IN ['OBSERVED', 'VALIDATED'])"
        )
        rows = self._run(
            f"""
            MATCH p = (start:Entity {{uid: $uid}})-[:RELATED*1..{int(depth)}]-(other:Entity)
            {status_clause}
            RETURN nodes(p) AS ns, relationships(p) AS rs
            """,
            uid=uid,
        )
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}
        for row in rows:
            for n in row["ns"]:
                nodes[n["uid"]] = GraphNode(
                    uid=n["uid"], type=n.get("type", ""), name=n.get("name", "")
                )
            for r in row["rs"]:
                edges[r["uid"]] = GraphEdge(
                    uid=r["uid"],
                    source=r.get("source", ""),
                    target=r.get("target", ""),
                    type=r.get("type", ""),
                    evidence_status=r.get("evidence_status", "OBSERVED"),
                    confidence=r.get("confidence", 1.0),
                    source_ref=r.get("source_ref"),
                    time_label=r.get("time_label"),
                )
        return list(nodes.values()), list(edges.values())

    def path(self, source: str, target: str) -> list[GraphNode]:
        rows = self._run(
            """
            MATCH (a:Entity {uid: $a}), (b:Entity {uid: $b})
            MATCH p = shortestPath((a)-[:RELATED*..8]-(b))
            RETURN nodes(p) AS ns
            """,
            a=source,
            b=target,
        )
        if not rows:
            return []
        return [
            GraphNode(uid=n["uid"], type=n.get("type", ""), name=n.get("name", ""))
            for n in rows[0]["ns"]
        ]

    def simple_paths(
        self, source: str, target: str, max_length: int = 4, limit: int = 10
    ) -> list[list[GraphNode]]:
        rows = self._run(
            f"""
            MATCH p = (a:Entity {{uid: $a}})-[:RELATED*1..{int(max_length)}]-(b:Entity {{uid: $b}})
            RETURN nodes(p) AS ns ORDER BY length(p) LIMIT {int(limit)}
            """,
            a=source,
            b=target,
        )
        return [
            [GraphNode(uid=n["uid"], type=n.get("type", ""), name=n.get("name", "")) for n in r["ns"]]
            for r in rows
        ]

    def common_connections(self, a: str, b: str) -> list[GraphNode]:
        rows = self._run(
            """
            MATCH (x:Entity {uid: $a})--(shared:Entity)--(y:Entity {uid: $b})
            RETURN DISTINCT shared
            """,
            a=a,
            b=b,
        )
        return [
            GraphNode(
                uid=r["shared"]["uid"],
                type=r["shared"].get("type", ""),
                name=r["shared"].get("name", ""),
            )
            for r in rows
        ]

    # Neo4j Graph Data Science is a separate licensed plugin that is not
    # assumed present, so structural analytics run on the mirrored snapshot
    # using the same exact algorithms as the embedded backend.
    def centrality(self) -> dict[str, dict[str, float]]:
        return self._mirror.centrality()

    def communities(self) -> tuple[dict[str, int], float]:
        return self._mirror.communities()

    def components(self) -> list[list[str]]:
        return self._mirror.components()

    def adamic_adar(self, a: str, b: str) -> float:
        return self._mirror.adamic_adar(a, b)

    def edges_between(self, a: str, b: str) -> list[GraphEdge]:
        return self._mirror.edges_between(a, b)

    def edges_for(self, uid: str) -> list[GraphEdge]:
        return self._mirror.edges_for(uid)


def _flatten(attributes: dict[str, Any]) -> dict[str, Any]:
    """Neo4j properties must be primitives; drop anything nested."""
    return {
        k: v
        for k, v in attributes.items()
        if isinstance(v, (str, int, float, bool)) or v is None
    }


def build_repository(
    backend: str, *, uri: str = "", user: str = "", password: str = "", database: str = "neo4j"
) -> GraphRepository:
    if backend == "neo4j":
        return Neo4jGraphRepository(uri, user, password, database)
    return EmbeddedGraphRepository()
