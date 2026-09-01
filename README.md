# TRINETRA

**AI-Powered Criminal Network Intelligence Platform**
*Connecting Data. Revealing Networks. Empowering Investigations.*

Smart India Hackathon 2026 — Problem Statement **26189**
Ministry of Home Affairs · National Crime Records Bureau · Women Safety Division

---

TRINETRA turns fragmented investigative records — FIRs, call detail records,
financial statements, surveillance reports — into a queryable knowledge graph,
surfaces connections that siloed records hide, and puts every AI-derived finding
in front of an authorised investigator before it can enter a case record.

It is a **decision-support system**. It does not determine guilt, and no screen
in it presents an inference as an established fact.

---

## Quick start

Requires **Python 3.11+** (developed and tested on 3.14). Nothing else — no
Node, no Docker, no database server.

```bash
cd TriNetra
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env          # then set SECRET_KEY
```

Seed the database (creates the schema, loads both demo cases, generates the
background corpus and writes the account credentials):

```bash
.venv/Scripts/python.exe backend/app/db/seed_bulk.py
```

Run it:

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --port 8000
```

Open **http://localhost:8000** and sign in with a Service ID from the generated
`CREDENTIALS.md` (gitignored — it is the only plaintext copy of the passwords).

| Service ID | Role | What it demonstrates |
|---|---|---|
| `IO-114` | Investigating Officer | The main investigation workflow |
| `WSO-052` | Women Safety Officer | SOS dispatch, heatmap, patterns |
| `SI-207` | Supervisory Officer | Case closure, assignment, audit |
| `AN-331` | Intelligence Analyst | Analysis without validation rights |
| `ADM-001` | NCRB Administrator | Audit log, roster, system health |

Signing in as different roles is the fastest way to see that RBAC is enforced
by the server rather than by hiding buttons.

## Sharing it with other people

`uvicorn --host 127.0.0.1` reaches your machine only. To let others in:

```powershell
.\share.ps1
```

This binds to every interface and prints a URL like `http://10.3.168.191:8000`
for anyone on the same Wi-Fi — phones and tablets included. Allow the Windows
Firewall prompt on **Private** networks the first time.

For a public link, sharing the code, or a permanent cloud deployment, see
[docs/SHARING.md](docs/SHARING.md). One gotcha worth knowing up front: keep
`ENVIRONMENT=development` when serving over plain HTTP, because production mode
marks the session cookie Secure and browsers then discard it.

---

## What actually works

Every item below is wired end to end — the UI calls a real endpoint, which
reads or writes the real database, and the result is reflected everywhere else.

**Investigation**
- Secure sign-in with scrypt hashing, JWT access + rotating refresh tokens,
  account lockout, session expiry and a full audit trail
- Role-based access control across 5 roles, enforced on every endpoint
- Interactive dashboard where every widget is computed live and every widget
  is a doorway into its detail page with the filter already applied
- Entity search across names, aliases and normalised identifiers
- Entity profiles: relationships, cases, timeline, evidence, priority
- Knowledge graph with 1/2/3-hop expansion, path finding, common connections,
  filtering, highlighting — observed edges solid, inferred edges dashed
- Graph analytics: degree, betweenness and closeness centrality, Louvain
  community detection, connected components
- Hidden-link discovery with Adamic-Adar weighting, each result carrying its
  reason, supporting records and confidence
- Entity resolution proposing alias matches with per-factor scoring; nothing
  merges without an investigator decision
- Investigation Priority Score — seven weighted factors, each computed from
  stored records and each citing its evidence
- Case management with a real status lifecycle, notes, team and entity links
- Timeline built from stored events, each resolving to its source record
- Data ingestion: validate → parse → clean → normalise → deduplicate →
  extract → resolve → relate → store → graph update, with counters computed
  from the uploaded file
- AI/NLP extraction from unstructured text, anchored to character spans so the
  UI highlights exactly which words produced each entity
- Report generation compiled from stored case data → HTML preview, real PDF, JSON
- Append-only audit log with filtering and CSV export

**Women Safety Intelligence**
- SOS with a real `RECEIVED → ASSIGNED → RESPONDING → RESOLVED` workflow,
  forward-only transitions, full status history and a dispatcher console
- Safety heatmap: severity-weighted kernel density per zone, recoloured on
  every filter change (type, severity, time of day, period)
- AI Safe Route: Yen's k-shortest paths over a waypoint graph whose cost blends
  distance, incident density, recent alerts, time of day, lighting and
  emergency-service proximity — with a per-factor score breakdown
- Suspicious pattern detection across shared vehicles, devices, locations and
  entities, linked back into the network graph
- Repeated-encounter detection over person / vehicle / location / time /
  device co-occurrence, citing the actual events that produced the finding
- Nearby police, hospitals, response units and safe locations
- Live alert feed over WebSocket with a polling fallback

---

## Architecture

```
React (no-build, htm)  ->  FastAPI  ->  RBAC + audit  ->  services
                                                            |
                              SQLAlchemy (SQLite/PostgreSQL)-+
                                                            |
                                    GraphRepository ---------+
                                     |            |
                              embedded engine   Neo4j (Cypher)
```

```
backend/app/     API, services, models, security
frontend/        client (vendored React + htm, no build step)
ai/              trinetra_nlp (extraction) · trinetra_er (resolution)
graph/           trinetra_graph (algorithms · repository · Neo4j adapter)
database/        seed data, corpus generator, source files
tests/           pytest suites + end-to-end workflow verification
docs/            architecture, security, integrations, data classification
legacy-prototype/ the original static prototype, preserved
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full picture, including
the substitution points for Neo4j, PostgreSQL and a statistical NLP model.

---

## Testing

```bash
.venv/Scripts/python.exe -m pytest              # 63 unit and API tests
```

With the server running, the full investigator journey can be verified too:

```bash
.venv/Scripts/python.exe tests/test_e2e_workflow.py    # 61 checks
```

The end-to-end script asserts the things that matter: that dashboard figures
match a direct database query, that a lower-privileged role receives 403 from
the server, that an investigator decision changes stored state, that the SOS
workflow transitions for real and refuses illegal transitions, and that a
re-uploaded file is deduplicated.

---

## Honesty about scope

This matters more than the feature list.

- **All data is synthetic.** Both demo cases and the generated background
  corpus are fictional. Every row carries a `data_classification` and the
  banner stays on until a deployment loads authorised data. See
  [docs/DATA_CLASSIFICATION.md](docs/DATA_CLASSIFICATION.md).
- **The Delhi crime statistics are real, cited and used for context only.**
  They never enter any analytical computation.
- **No external service is connected.** Device GPS, emergency dispatch, SMS,
  telecom CDR feeds, RTO lookup and CCTNS sync are structured with real
  interfaces and data contracts but are switched off and clearly labelled.
  Raising an SOS notifies this platform's console and nothing else. See
  [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).
- **Neo4j is implemented, not simulated** — real Cypher, constraints and
  indexes — but the default `embedded` backend is what runs here, because no
  Neo4j instance is present. Both satisfy the same interface.
- **The NLP pipeline is rule-based**, deterministic and explainable. No
  statistical model is bundled and none is claimed. The `NlpEngine` interface
  exists so one can be substituted.
- **On large graphs, betweenness and closeness are estimated** from a seeded
  pivot sample, and the API says so. Degree centrality and community detection
  remain exact.
- **The platform is not certified secure.** See
  [docs/SECURITY.md](docs/SECURITY.md) for what is implemented and what a real
  deployment would still need.

---

**TRINETRA is an investigative decision-support system. It does not determine
guilt and does not replace authorised human judgement.**
