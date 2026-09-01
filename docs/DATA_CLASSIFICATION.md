# Data Classification

Every row in TRINETRA carries a classification. This exists so that no figure,
chart or report can be mistaken for operational police data.

## Classes

| Class | Meaning | Present here |
|---|---|---|
| `SYNTHETIC` | Generated or fictional data for demonstration and testing | **Yes — everything except the context statistics** |
| `REFERENCE` | Real, publicly published, cited statistics used for context only | **Yes — the Delhi crime figures** |
| `OPERATIONAL` | Authorised real case data | **No. Never present in this build.** |

## What is synthetic

Everything the platform analyses:

- **Case `NX-2026-0147`** (Financial Network Investigation) — all people,
  phones, organisations, vehicles and transactions are fictional.
- **Case `DEMO/WS-2026-0417`** (Stalking & Harassment) — the victim, suspects,
  witness, phone numbers, vehicle, social handle and locations are fictional.
  The source file labels itself `synthetic_demo_only`.
- **The background corpus** — approximately 3,000 entities and 8,500
  relationships from a deterministic seeded generator. Names are ordinary Indian
  given names and surnames combined at random; any resemblance to a real person
  is coincidental and unintended.
- **Safety zones, emergency services and waypoints** — fictional demonstration
  locations. The coordinates are approximate centroids of real localities, used
  so that distance, density and routing operate on real geometry. They are not
  real addresses and no real police station or hospital is represented.

## What is real

**Only the Delhi crime-against-women statistics** shown on the Women Safety
overview:

- 13,366 total crimes against women reported in Delhi in 2023
- ~4,000 kidnapping and abduction cases in 2023
- Year-on-year and quarterly comparisons for rape, molestation and eve-teasing

Sources: NCRB and Delhi Police figures as reported by Deccan Herald and The
Tribune.

These are classified `REFERENCE`, displayed only as problem context, visually
separated from case data, carry their source on screen, and **are never used in
any analytical computation** — not in scoring, not in the heatmap, not in
pattern detection, not in reports.

## Controls

1. **Row-level labelling.** `data_classification` is a column on entities,
   relationships, records, evidence, incidents, alerts, zones and services.
2. **A persistent banner** on every screen while `DATA_CLASSIFICATION` is
   `SYNTHETIC`. It is a data-integrity control, not decoration — it is not
   dismissible and stays on until a deployment loads authorised data.
3. **Report headers.** Every generated report carries the classification notice
   in its header, in the PDF as well as the preview.
4. **Separation in the UI.** Reference statistics appear under their own
   heading with an explicit disclaimer and their citation.

## If you load real data

1. Establish and record the lawful basis and authorisation for each source.
2. Set `DATA_CLASSIFICATION=OPERATIONAL` and write `OPERATIONAL` on ingested
   rows.
3. Work through `docs/SECURITY.md` first — the deployment checklist there is
   not optional once real data is involved.
4. Never mix synthetic and operational rows in one database.
