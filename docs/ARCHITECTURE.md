# Architecture

```
                    React client (no build step)
                    vendored React 18 + htm + Cytoscape
                              |  REST + WebSocket
                              v
                        FastAPI application
             CORS · security headers · error envelope · rate limit
                              |
                    Authentication (JWT) + RBAC
                              |
                       Service layer
     graph · priority · discovery · patterns · safety · ingestion · audit
                    /                    |                 \
       SQLAlchemy ORM            GraphRepository        NlpEngine
    SQLite | PostgreSQL      embedded | Neo4j        rule-based | (spaCy)
```

## Principle: one source of truth

The relational database is the system of record. The knowledge graph is a
**projection** of it, not a second copy.

- `graph_service._project()` reads entities and relationships and builds the
  graph.
- Every write path that changes them calls `graph_service.invalidate()`.
- The next graph query rebuilds the projection.

This is what makes DESIGN.md's data-consistency requirement hold: validate a
relationship and the dashboard, search, graph, analytics, timeline and reports
all change together, because they all read the same rows.

The projection deliberately excludes:
- entities deactivated by an accepted entity-resolution merge, and
- relationships an investigator has rejected

so a decision genuinely removes something from analysis rather than relabelling it.

## Substitution points

Each of these is an interface with more than one real implementation, so the
component can be replaced by configuration rather than by editing callers.

| Interface | Default | Alternative |
|---|---|---|
| `GraphRepository` | `EmbeddedGraphRepository` (pure Python) | `Neo4jGraphRepository` (Cypher) |
| `DATABASE_URL` | SQLite | PostgreSQL |
| `NlpEngine` | `RuleBasedEngine` | a spaCy/transformer implementation |
| Map base layer | self-contained SVG | XYZ tiles via `MAP_TILE_URL` |

## Analytics caching

Structural analytics (centrality, communities, components) are computed once per
graph version and cached. Without this, a single request recomputing betweenness
over a few thousand nodes holds the GIL for a minute and starves every other
request — this was measured, not assumed.

On graphs above `EXACT_CENTRALITY_LIMIT` (700 nodes), betweenness and closeness
switch to a seeded pivot sample. That is deterministic and suitable for ranking,
but the values are estimates and the API says so in `betweenness_note`. Degree
centrality and community detection remain exact at any size.

The cache is warmed in a background thread at startup so the first request to an
analytics page does not pay for it.

## Real-time

`services/realtime.py` is an in-process publish/subscribe hub. `/ws/events`
streams to connected clients; `/api/v1/events/poll` is the fallback the client
uses automatically when the socket drops, so a lost connection degrades the
experience rather than breaking it.

This is single-process only. Multiple workers would need a shared broker
(Redis pub/sub or equivalent) — stated here rather than pretended away.

## Request lifecycle

1. `security_headers` middleware assigns a request ID and sets response headers.
2. Rate limiter checks the caller's budget.
3. `get_current_user` verifies the JWT and loads the user.
4. `require_permission(...)` checks the role; a denial is audited and returns 403.
5. The handler runs against a request-scoped SQLAlchemy session.
6. Consequential actions write an audit entry in the same transaction.
7. Graph-affecting writes call `invalidate()`.
8. Errors are caught by the handlers in `main.py` and returned as a uniform
   envelope; the stack trace is logged server-side only.

## Why a no-build frontend

Node.js is not installed in the target environment, so Vite and TypeScript
cannot run. Rather than ship a frontend that cannot be executed or tested, the
client uses React 18 with `htm` — tagged template literals instead of JSX —
vendored locally. It is genuine React: components, hooks, context, an error
boundary, a router.

The trade-off is explicit: no TypeScript and no bundler. The source is split
into components and pages exactly as a Vite project would be, so converting it
is mechanical if Node becomes available.
