# External Integrations — Status

Every external touchpoint TRINETRA is designed around is listed here with its
honest status. Nothing in this document describes a connection that exists.

**None of the integrations below are connected.** Each is structured — the data
model, the service interface and the call sites exist — but each is disabled by
a configuration flag and requires authorisation, credentials and configuration
before it could be enabled. The UI reads these flags and labels its capabilities
accordingly rather than implying a live connection.

---

## Status summary

| Integration | Flag | Status | What exists today |
|---|---|---|---|
| Device GPS | `ENABLE_DEVICE_GPS` | **Not connected** | SOS positions are entered manually and stored with `location_source = SIMULATED`, shown as such in the UI |
| Emergency dispatch | `ENABLE_EMERGENCY_DISPATCH` | **Not connected** | SOS alerts reach this platform's operations console only |
| SMS / push notification | `ENABLE_SMS_GATEWAY` | **Not connected** | Emergency contacts are recorded and listed; no message is sent |
| Telecom CDR feed | `ENABLE_TELECOM_CDR_FEED` | **Not connected** | CDR data enters by manual CSV upload |
| RTO / vehicle lookup | `ENABLE_RTO_LOOKUP` | **Not connected** | Vehicle records come from uploaded files and seed data |
| CCTNS / cross-district FIR | `ENABLE_CCTNS_SYNC` | **Not connected** | Prior-case links come from seeded records |
| Map tiles | `MAP_TILE_URL` | **Off by default** | Self-contained SVG renderer; set the variable to overlay real tiles |
| Neo4j | `GRAPH_BACKEND` | **Implemented, not running here** | Full Cypher adapter; `embedded` engine is the default |
| PostgreSQL | `DATABASE_URL` | **Supported, not running here** | SQLAlchemy; SQLite is the default |

---

## What each would require

### Device GPS
A browser or mobile client supplying a position via the Geolocation API, plus
explicit user consent. The `SosAlert` model already carries `latitude`,
`longitude` and `location_source`; enabling the flag switches new alerts from
`SIMULATED` to `DEVICE`. **Until then the platform must not imply it knows where
anyone is.**

### Emergency dispatch
An authorised interface to a police control room or 112/1091 dispatch system.
This is the integration with the greatest potential for harm if misrepresented:
a user who believes help has been summoned when it has not is worse off than one
who knows they must call. The SOS screen therefore states plainly that no
emergency call is placed.

Required: an authorised endpoint, a service agreement, message-format
agreement, delivery confirmation, and an escalation path when dispatch fails.

### SMS / push notification
A licensed gateway (DLT-registered sender ID for Indian SMS) with consent
records for each contact. `EmergencyContact` rows exist and are displayed on the
alert; enabling this would send to them in priority order.

### Telecom CDR feed
Lawful-interception or authorised-disclosure channel under the applicable legal
process. CDR content is highly sensitive and its ingestion must be tied to a
specific authorisation reference. The ingestion pipeline already records a
source reference per record, which is where that authorisation would be
captured.

### RTO / vehicle registration lookup
Authorised access to the vehicle registration database. The `vehicle` entity
type and `registered_owner_of` relationship already model the result.

### CCTNS / cross-district FIR
The cross-district linkage that the Women Safety demo case turns on — matching
a suspect to a prior FIR in another district — is exactly what this would
provide in a real deployment. Here it comes from seeded records.

### Map tiles
Set `MAP_TILE_URL` to an XYZ template and `MAP_ATTRIBUTION` to the required
attribution string. Left empty, the platform renders a self-contained map that
works with no internet connection. The base layer is a coordinate grid, not a
street map: it shows relative position honestly rather than implying
cartographic detail the platform does not have.

### Neo4j
```bash
docker compose up -d neo4j
# .env:
GRAPH_BACKEND=neo4j
NEO4J_PASSWORD=<your password>
```
`Neo4jGraphRepository` is a complete implementation — real Cypher, uniqueness
constraints, indexes, parameterised queries — behind the same `GraphRepository`
interface as the embedded engine. It has not been exercised against a live
server in this environment, so treat the first run as needing verification.

Structural analytics run on the mirrored in-process snapshot in both backends,
because Neo4j Graph Data Science is a separately licensed plugin that is not
assumed to be present.

### PostgreSQL
```bash
docker compose up -d postgres
# .env:
DATABASE_URL=postgresql+psycopg://trinetra:trinetra@localhost:5432/trinetra
```
Requires `pip install psycopg[binary]`. No model changes are needed.

---

## Rule for contributors

If you connect one of these, update this table in the same change. A stale
"not connected" is a lie in the other direction, and this document is only
worth having if it is exactly true.
