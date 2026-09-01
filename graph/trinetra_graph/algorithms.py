"""Graph algorithms, implemented in pure Python over an adjacency mapping.

Every function here is deterministic: repeated runs on the same graph produce
identical output, which matters because an investigator must be able to
re-derive any figure the platform showed them.

All are exact except betweenness_centrality when given a `pivots` argument,
which switches to the seeded Brandes-Pich estimator for graphs too large to
compute exactly inside a request. That path is still deterministic, and callers
label its output as estimated.

The adjacency form used throughout is:

    adj: dict[NodeId, dict[NodeId, list[EdgeRef]]]

i.e. an undirected multigraph where each neighbour maps to the list of edges
connecting the pair. Direction is preserved on the edge records themselves.
"""

from __future__ import annotations

import heapq
import random
from collections import defaultdict, deque
from collections.abc import Callable, Hashable, Iterable, Sequence
from typing import Any

NodeId = Hashable
Adjacency = dict[NodeId, dict[NodeId, list[Any]]]


def build_adjacency(
    nodes: Iterable[NodeId],
    edges: Iterable[tuple[NodeId, NodeId, Any]],
) -> Adjacency:
    """Build an undirected multigraph adjacency from nodes and (u, v, ref)."""
    adj: Adjacency = {n: {} for n in nodes}
    for u, v, ref in edges:
        if u not in adj or v not in adj:
            continue
        if u == v:
            continue  # self-loops carry no relational meaning here
        adj[u].setdefault(v, []).append(ref)
        adj[v].setdefault(u, []).append(ref)
    return adj


# ---------------------------------------------------------------- traversal


def k_hop(
    adj: Adjacency,
    start: NodeId,
    depth: int = 1,
    edge_filter: Callable[[Any], bool] | None = None,
) -> dict[NodeId, int]:
    """Return {node: hop_distance} for every node within `depth` hops.

    The start node is included at distance 0.
    """
    if start not in adj:
        return {}
    seen: dict[NodeId, int] = {start: 0}
    frontier = deque([start])
    while frontier:
        node = frontier.popleft()
        d = seen[node]
        if d >= depth:
            continue
        for neighbour, refs in adj[node].items():
            if edge_filter is not None and not any(edge_filter(r) for r in refs):
                continue
            if neighbour not in seen:
                seen[neighbour] = d + 1
                frontier.append(neighbour)
    return seen


def shortest_path(
    adj: Adjacency,
    source: NodeId,
    target: NodeId,
    edge_filter: Callable[[Any], bool] | None = None,
) -> list[NodeId]:
    """Unweighted shortest path as a node list. Empty if unreachable."""
    if source not in adj or target not in adj:
        return []
    if source == target:
        return [source]
    previous: dict[NodeId, NodeId] = {source: source}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for neighbour, refs in adj[node].items():
            if edge_filter is not None and not any(edge_filter(r) for r in refs):
                continue
            if neighbour in previous:
                continue
            previous[neighbour] = node
            if neighbour == target:
                path = [target]
                while path[-1] != source:
                    path.append(previous[path[-1]])
                return list(reversed(path))
            queue.append(neighbour)
    return []


def all_simple_paths(
    adj: Adjacency,
    source: NodeId,
    target: NodeId,
    max_length: int = 4,
    limit: int = 25,
) -> list[list[NodeId]]:
    """Enumerate simple paths up to `max_length` edges, shortest first."""
    if source not in adj or target not in adj or source == target:
        return []
    results: list[list[NodeId]] = []
    stack: list[tuple[list[NodeId], set[NodeId]]] = [([source], {source})]
    while stack and len(results) < limit:
        path, visited = stack.pop(0)
        if len(path) - 1 >= max_length:
            continue
        for neighbour in adj[path[-1]]:
            if neighbour == target:
                results.append([*path, target])
                if len(results) >= limit:
                    break
            elif neighbour not in visited:
                stack.append(([*path, neighbour], visited | {neighbour}))
    results.sort(key=len)
    return results


def common_neighbors(adj: Adjacency, a: NodeId, b: NodeId) -> list[NodeId]:
    if a not in adj or b not in adj:
        return []
    return sorted(set(adj[a]) & set(adj[b]), key=str)


# --------------------------------------------------------------- centrality


def degree_centrality(adj: Adjacency, weighted: bool = False) -> dict[NodeId, float]:
    """Degree, normalised by the maximum possible degree (n-1).

    With weighted=True, parallel edges each count, so an entity contacted 12
    times ranks above one contacted once.
    """
    n = len(adj)
    if n <= 1:
        return dict.fromkeys(adj, 0.0)
    out: dict[NodeId, float] = {}
    for node, neighbours in adj.items():
        raw = (
            sum(len(refs) for refs in neighbours.values()) if weighted else len(neighbours)
        )
        out[node] = raw / (n - 1)
    return out


def betweenness_centrality(
    adj: Adjacency,
    normalized: bool = True,
    pivots: int | None = None,
    seed: int = 26189,
) -> dict[NodeId, float]:
    """Brandes' algorithm for unweighted graphs.

    Identifies brokers - entities that sit on the paths between otherwise
    disconnected parts of a network. Often more investigatively interesting
    than raw degree.

    Exact Brandes is O(V*E), which on a graph of a few thousand nodes runs for
    a minute or more in pure Python and blocks everything else. Passing
    `pivots` runs the Brandes-Pich estimator instead: accumulate from a random
    but *seeded* sample of source nodes and scale by V/k. Deterministic for a
    given graph and seed, and callers are expected to label the result as
    estimated rather than presenting it as exact.
    """
    betweenness: dict[NodeId, float] = dict.fromkeys(adj, 0.0)

    sources: list[NodeId] = sorted(adj, key=str)
    if pivots is not None and 0 < pivots < len(sources):
        sources = random.Random(seed).sample(sources, pivots)
        scale_for_sampling = len(adj) / len(sources)
    else:
        scale_for_sampling = 1.0

    for s in sources:
        stack: list[NodeId] = []
        predecessors: dict[NodeId, list[NodeId]] = {w: [] for w in adj}
        sigma: dict[NodeId, float] = dict.fromkeys(adj, 0.0)
        sigma[s] = 1.0
        distance: dict[NodeId, int] = {s: 0}
        queue = deque([s])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adj[v]:
                if w not in distance:
                    distance[w] = distance[v] + 1
                    queue.append(w)
                if distance[w] == distance[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)
        delta: dict[NodeId, float] = dict.fromkeys(adj, 0.0)
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                if sigma[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                betweenness[w] += delta[w]
    n = len(adj)
    # Undirected: each pair is counted twice. When sampling, scale the partial
    # accumulation up to an estimate of the full-graph value.
    for node in betweenness:
        betweenness[node] = betweenness[node] / 2.0 * scale_for_sampling
    if normalized and n > 2:
        scale = 2.0 / ((n - 1) * (n - 2))
        for node in betweenness:
            betweenness[node] *= scale
    return betweenness


def closeness_centrality(
    adj: Adjacency, pivots: int | None = None, seed: int = 26189
) -> dict[NodeId, float]:
    """Wasserman-Faust closeness, which handles disconnected graphs.

    Exact computation runs a BFS from every node - O(V*E), the same cost as
    exact betweenness. `pivots` switches to the Eppstein-Wang estimator: BFS
    from a seeded sample of sources and estimate every node's closeness from
    the distances observed. The graph is undirected, so a BFS from a pivot
    yields that pivot's distance to every node in both directions.

    With pivots=None this is exact and returns identical values to a
    per-node BFS.
    """
    n = len(adj)
    if n == 0:
        return {}

    sources: list[NodeId] = sorted(adj, key=str)
    if pivots is not None and 0 < pivots < len(sources):
        sources = random.Random(seed).sample(sources, pivots)

    total_distance: dict[NodeId, float] = dict.fromkeys(adj, 0.0)
    reached_by: dict[NodeId, int] = dict.fromkeys(adj, 0)

    for source in sources:
        for target, distance in _bfs_distances(adj, source).items():
            if target == source:
                continue
            total_distance[target] += distance
            reached_by[target] += 1

    # Denominator: how many of the sampled sources could have reached this
    # node. With a full sweep that is n-1, matching the exact formulation.
    sample_size = len(sources)
    out: dict[NodeId, float] = {}
    for node in adj:
        reachable = reached_by[node]
        total = total_distance[node]
        if reachable == 0 or total == 0:
            out[node] = 0.0
            continue
        denominator = (n - 1) if sample_size >= n else sample_size
        out[node] = (reachable / total) * (reachable / denominator)
    return out


def _bfs_distances(adj: Adjacency, start: NodeId) -> dict[NodeId, int]:
    distances = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbour in adj[node]:
            if neighbour not in distances:
                distances[neighbour] = distances[node] + 1
                queue.append(neighbour)
    return distances


# --------------------------------------------------------------- structure


def connected_components(adj: Adjacency) -> list[list[NodeId]]:
    seen: set[NodeId] = set()
    components: list[list[NodeId]] = []
    for start in adj:
        if start in seen:
            continue
        component: list[NodeId] = []
        queue = deque([start])
        seen.add(start)
        while queue:
            node = queue.popleft()
            component.append(node)
            for neighbour in adj[node]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        components.append(sorted(component, key=str))
    components.sort(key=len, reverse=True)
    return components


def _louvain_local_moving(
    weights: dict[Any, dict[Any, float]],
    self_loops: dict[Any, float],
    resolution: float,
    total_weight: float,
) -> dict[Any, int]:
    """One level of Louvain: move nodes greedily until modularity stalls."""
    community = {node: idx for idx, node in enumerate(sorted(weights, key=str))}
    strength = {
        node: sum(w.values()) + 2 * self_loops.get(node, 0.0) for node, w in weights.items()
    }
    community_strength: dict[int, float] = defaultdict(float)
    for node, comm in community.items():
        community_strength[comm] += strength[node]

    for _ in range(30):
        moved = False
        for node in sorted(weights, key=str):
            current = community[node]
            community_strength[current] -= strength[node]

            links: dict[int, float] = defaultdict(float)
            for neighbour, weight in weights[node].items():
                if neighbour != node:
                    links[community[neighbour]] += weight

            best_comm = current
            best_gain = links.get(current, 0.0) - resolution * community_strength[
                current
            ] * strength[node] / (2.0 * total_weight)
            for comm, link_weight in links.items():
                if comm == current:
                    continue
                gain = link_weight - resolution * community_strength[comm] * strength[node] / (
                    2.0 * total_weight
                )
                if gain > best_gain + 1e-12:
                    best_gain, best_comm = gain, comm

            community_strength[best_comm] += strength[node]
            if best_comm != current:
                community[node] = best_comm
                moved = True
        if not moved:
            break
    return community


def louvain_communities(adj: Adjacency, resolution: float = 1.0) -> dict[NodeId, int]:
    """Multi-level Louvain modularity maximisation.

    Runs the full algorithm: local moving, then graph coarsening where each
    community collapses to a single node, repeated until modularity stops
    improving. Local moving alone stalls in a local optimum and leaves a large
    graph fragmented into hundreds of tiny communities.

    Node iteration order is sorted throughout, so results are reproducible
    rather than dependent on dict ordering across runs.
    """
    total_weight = sum(len(refs) for nbrs in adj.values() for refs in nbrs.values()) / 2.0
    if total_weight == 0:
        return {node: idx for idx, node in enumerate(sorted(adj, key=str))}

    # Level 0 working graph.
    weights: dict[Any, dict[Any, float]] = {
        node: {nbr: float(len(refs)) for nbr, refs in nbrs.items()}
        for node, nbrs in adj.items()
    }
    self_loops: dict[Any, float] = dict.fromkeys(weights, 0.0)
    # Maps every original node to its node in the current (coarsened) graph.
    membership: dict[NodeId, Any] = {node: node for node in adj}

    previous_q = -1.0
    for _ in range(10):
        level = _louvain_local_moving(weights, self_loops, resolution, total_weight)
        # Collapse: each community becomes one node in the next level.
        membership = {node: level[current] for node, current in membership.items()}

        if len(set(level.values())) == len(level):
            break  # nothing merged - converged

        new_weights: dict[Any, dict[Any, float]] = defaultdict(lambda: defaultdict(float))
        new_self: dict[Any, float] = defaultdict(float)
        for node, nbrs in weights.items():
            cn = level[node]
            new_self[cn] += self_loops.get(node, 0.0)
            for neighbour, weight in nbrs.items():
                cm = level[neighbour]
                if cn == cm:
                    new_self[cn] += weight / 2.0
                else:
                    new_weights[cn][cm] += weight
        weights = {n: dict(m) for n, m in new_weights.items()}
        for community_node in set(level.values()):
            weights.setdefault(community_node, {})
        self_loops = dict(new_self)

        q = modularity(adj, _compact(membership))
        if q <= previous_q + 1e-9:
            break
        previous_q = q

    return _compact(membership)


def _compact(membership: dict[NodeId, Any]) -> dict[NodeId, int]:
    """Renumber community labels to 0..k-1, largest community first."""
    sizes: dict[Any, int] = defaultdict(int)
    for comm in membership.values():
        sizes[comm] += 1
    ordering = sorted(sizes, key=lambda c: (-sizes[c], str(c)))
    remap = {old: new for new, old in enumerate(ordering)}
    return {node: remap[comm] for node, comm in membership.items()}


def modularity(adj: Adjacency, community: dict[NodeId, int]) -> float:
    """Newman modularity of a partition - how well-separated the clusters are."""
    m = sum(len(refs) for nbrs in adj.values() for refs in nbrs.values()) / 2.0
    if m == 0:
        return 0.0
    degrees = {n: sum(len(r) for r in nbrs.values()) for n, nbrs in adj.items()}
    internal: dict[int, float] = defaultdict(float)
    total_degree: dict[int, float] = defaultdict(float)
    for node, nbrs in adj.items():
        c = community.get(node)
        total_degree[c] += degrees[node]
        for neighbour, refs in nbrs.items():
            if community.get(neighbour) == c:
                internal[c] += len(refs)
    q = 0.0
    for c in total_degree:
        q += (internal[c] / (2.0 * m)) - (total_degree[c] / (2.0 * m)) ** 2
    return q


# ------------------------------------------------------- link prediction


def adamic_adar_score(adj: Adjacency, a: NodeId, b: NodeId) -> float:
    """Adamic-Adar index: shared neighbours weighted by how rare they are.

    A shared contact who knows only these two people is far more telling than
    a hub connected to hundreds, and this weighting captures that.
    """
    import math

    shared = set(adj.get(a, {})) & set(adj.get(b, {}))
    score = 0.0
    for node in shared:
        degree = len(adj[node])
        if degree > 1:
            score += 1.0 / math.log(degree)
    return score


def weighted_shortest_path(
    adj: Adjacency,
    source: NodeId,
    target: NodeId,
    cost: Callable[[NodeId, NodeId, list[Any]], float],
) -> tuple[list[NodeId], float]:
    """Dijkstra over a caller-supplied cost function.

    Used by the safe-route engine, where cost blends distance with safety
    signals rather than being pure geography.
    """
    if source not in adj or target not in adj:
        return [], float("inf")
    dist: dict[NodeId, float] = {source: 0.0}
    previous: dict[NodeId, NodeId] = {}
    heap: list[tuple[float, int, NodeId]] = [(0.0, 0, source)]
    counter = 0
    visited: set[NodeId] = set()
    while heap:
        d, _, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == target:
            break
        for neighbour, refs in adj[node].items():
            if neighbour in visited:
                continue
            nd = d + cost(node, neighbour, refs)
            if nd < dist.get(neighbour, float("inf")):
                dist[neighbour] = nd
                previous[neighbour] = node
                counter += 1
                heapq.heappush(heap, (nd, counter, neighbour))
    if target not in dist:
        return [], float("inf")
    path = [target]
    while path[-1] != source:
        path.append(previous[path[-1]])
    return list(reversed(path)), dist[target]


def k_shortest_paths(
    adj: Adjacency,
    source: NodeId,
    target: NodeId,
    cost: Callable[[NodeId, NodeId, list[Any]], float],
    k: int = 3,
) -> list[tuple[list[NodeId], float]]:
    """Yen's algorithm - the k cheapest loopless paths under `cost`.

    The safe-route feature needs genuinely distinct alternatives to compare,
    not one path plus arbitrary detours.
    """
    first, first_cost = weighted_shortest_path(adj, source, target, cost)
    if not first:
        return []
    accepted: list[tuple[list[NodeId], float]] = [(first, first_cost)]
    candidates: list[tuple[float, list[NodeId]]] = []

    while len(accepted) < k:
        previous_path = accepted[-1][0]
        for i in range(len(previous_path) - 1):
            spur_node = previous_path[i]
            root_path = previous_path[: i + 1]

            removed: list[tuple[NodeId, NodeId, list[Any]]] = []
            for path, _ in accepted:
                if len(path) > i and path[: i + 1] == root_path:
                    u, v = path[i], path[i + 1]
                    if v in adj.get(u, {}):
                        removed.append((u, v, adj[u][v]))
                        del adj[u][v]
                        if u in adj.get(v, {}):
                            del adj[v][u]

            blocked: dict[NodeId, dict[NodeId, list[Any]]] = {}
            for node in root_path[:-1]:
                blocked[node] = adj.pop(node, {})
                for other in adj.values():
                    other.pop(node, None)

            spur_path, _ = weighted_shortest_path(adj, spur_node, target, cost)

            for node, nbrs in blocked.items():
                adj[node] = nbrs
                for nbr in nbrs:
                    if nbr in adj:
                        adj[nbr][node] = nbrs[nbr]
            for u, v, refs in removed:
                adj[u][v] = refs
                adj[v][u] = refs

            if spur_path:
                total = root_path[:-1] + spur_path
                if not any(total == p for p, _ in accepted) and not any(
                    total == p for _, p in candidates
                ):
                    total_cost = sum(
                        cost(total[j], total[j + 1], adj.get(total[j], {}).get(total[j + 1], []))
                        for j in range(len(total) - 1)
                    )
                    candidates.append((total_cost, total))

        if not candidates:
            break
        candidates.sort(key=lambda item: (item[0], len(item[1])))
        best_cost, best_path = candidates.pop(0)
        accepted.append((best_path, best_cost))

    return accepted


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    import math

    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
