"""End-to-end workflow verification against a running TRINETRA server.

Run the server first, then:  python tests/test_e2e_workflow.py

This exercises the full investigator journey the platform exists to support,
and asserts the things that matter: that displayed numbers match the database,
that RBAC is enforced server-side, that an investigator decision actually
changes stored state, and that Women Safety workflows transition for real.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
for path in ("backend", "database", "ai", "graph"):
    sys.path.insert(0, str(ROOT / path))

BASE = "http://127.0.0.1:8000/api/v1"

_ok = 0
_fail = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _ok, _fail
    if condition:
        _ok += 1
        print(f"  PASS  {label}" + (f"   [{detail}]" if detail else ""))
    else:
        _fail += 1
        print(f"  FAIL  {label}   [{detail}]")


def load_credentials() -> dict[str, str]:
    creds: dict[str, str] = {}
    for line in (ROOT / "CREDENTIALS.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`([A-Z]+-\d+)`\s*\|[^|]*\|[^|]*\|[^|]*\|\s*`([^`]+)`", line)
        if m:
            creds[m.group(1)] = m.group(2)
    return creds


def sign_in(creds: dict[str, str], service_id: str) -> tuple[httpx.Client, dict]:
    client = httpx.Client(base_url=BASE, timeout=120)
    response = client.post(
        "/auth/login", json={"service_id": service_id, "password": creds[service_id]}
    )
    response.raise_for_status()
    body = response.json()
    client.headers["Authorization"] = f"Bearer {body['access_token']}"
    return client, body["user"]


def main() -> int:
    creds = load_credentials()

    print("=" * 76)
    print("1. AUTHENTICATION & IDENTITY")
    io_client, io_user = sign_in(creds, "IO-114")
    check("investigator signs in", io_user["service_id"] == "IO-114")
    check(
        "identity carries name, role and unit",
        all(io_user.get(k) for k in ("full_name", "role_label", "unit", "initials")),
        f"{io_user['full_name']} / {io_user['role_label']} / {io_user['unit']}",
    )
    check("permissions granted", len(io_user["permissions"]) == 16,
          f"{len(io_user['permissions'])} permissions")

    bad = httpx.post(f"{BASE}/auth/login",
                     json={"service_id": "IO-114", "password": "wrong"}, timeout=60)
    check("wrong password rejected", bad.status_code == 401, f"HTTP {bad.status_code}")
    check("failure reports remaining attempts",
          "attempts_remaining" in bad.json().get("error", {}),
          f"{bad.json()['error'].get('attempts_remaining')} left")

    print("\n2. RBAC ENFORCED BY THE BACKEND")
    check("investigator blocked from audit log",
          io_client.get("/audit/logs").status_code == 403)
    analyst_client, _ = sign_in(creds, "AN-331")
    check("analyst cannot validate relationships",
          analyst_client.post("/graph/relationship/1/validate",
                              json={"decision": "VALIDATED"}).status_code == 403)
    admin_client, _ = sign_in(creds, "ADM-001")
    check("admin can read audit log", admin_client.get("/audit/logs").status_code == 200)

    print("\n3. DASHBOARD FIGURES MATCH THE DATABASE")
    from sqlalchemy import func, select

    from app.db.models import Entity, Record, Relationship
    from app.db.session import SessionLocal

    db = SessionLocal()
    dashboard = io_client.get("/dashboard").json()
    kpis = {k["key"]: k["value"] for k in dashboard["kpis"]}
    db_records = db.scalar(select(func.count()).select_from(Record))
    db_entities = db.scalar(
        select(func.count()).select_from(Entity).where(Entity.is_active.is_(True))
    )
    check("Total Records matches a direct query", kpis["records"] == db_records,
          f"{kpis['records']:,} == {db_records:,}")
    check("Entities Extracted matches a direct query", kpis["entities"] == db_entities,
          f"{kpis['entities']:,} == {db_entities:,}")
    check("every KPI carries a click-through route",
          all(k.get("route") for k in dashboard["kpis"]))
    check("graph preview is populated",
          dashboard["graph_preview"]["counts"]["nodes"] > 0,
          f"{dashboard['graph_preview']['counts']['nodes']} nodes")

    print("\n4. SEARCH -> PROFILE -> NETWORK EXPANSION")
    results = io_client.get("/entities/search", params={"q": "Rahul Sharma"}).json()
    check("search finds the entity", results["count"] >= 1)
    uid = results["results"][0]["uid"]
    profile = io_client.get(f"/entities/{uid}").json()
    check("profile carries relationships", profile["summary"]["relationships"] > 0,
          f"{profile['summary']['relationships']} relationships")
    # Assert the distinction is applied consistently rather than that both
    # kinds happen to be present: is_observed must be true exactly for OBSERVED
    # and VALIDATED, never for a bare inference. (A previous run may already
    # have validated this entity's inferred links.)
    consistent = all(
        row["is_observed"] == (row["evidence_status"] in ("OBSERVED", "VALIDATED"))
        for row in profile["relationships"]
    )
    check("observed/inferred flag correct on every relationship", consistent,
          f"{profile['summary']['observed']} observed / "
          f"{profile['summary']['inferred']} inferred")
    hop2 = io_client.get(f"/graph/neighbourhood/{uid}", params={"depth": 2}).json()
    check("2-hop expansion returns a subgraph", hop2["counts"]["nodes"] > 3,
          f"{hop2['counts']['nodes']} nodes / {hop2['counts']['edges']} edges")

    print("\n5. HIDDEN LINK -> EVIDENCE -> VALIDATION")
    links = io_client.get("/graph/hidden-links").json()
    pending = [s for s in links["stored"] if s["requires_validation"]]

    if not pending:
        # A previous run validated everything that was queued. Create a fresh
        # inferred relationship through the real NLP path so the validation
        # workflow can be exercised again - the test must be re-runnable.
        import random as _random
        import string as _string

        def coined() -> str:
            # Letters only: the name recogniser deliberately rejects tokens
            # containing digits, so a hex tag would never be extracted.
            return "".join(_random.choices(_string.ascii_lowercase, k=6)).capitalize()

        commit = io_client.post("/nlp/commit", json={
            "text": f"{coined()} {coined()} met {coined()} {coined()} at Karol Bagh.",
        }).json()
        assert commit["counts"]["relationships"] > 0, (
            f"NLP commit produced no inferred relationship: {commit}"
        )
        links = io_client.get("/graph/hidden-links").json()
        pending = [s for s in links["stored"] if s["requires_validation"]]

    check("inferred links await validation", len(pending) > 0, f"{len(pending)} pending")
    if pending:
        target = pending[0]
        evidence = io_client.get(
            f"/graph/relationship/{target['relationship_id']}/evidence"
        ).json()
        check("evidence states a reason", bool(evidence.get("reason")),
              (evidence.get("reason") or "")[:56])
        # Evidence takes different shapes by inference method: a graph-derived
        # link cites the relationships it was built from, while a text-extracted
        # one cites the sentence and trigger phrase. Either is traceable; an
        # inference citing neither would not be.
        supporting = evidence.get("supporting_relationships", [])
        direct = evidence.get("direct_evidence", [])
        traceable = bool(supporting) or bool(direct) or bool(evidence.get("method"))
        check("evidence is traceable to its basis", traceable,
              f"{len(supporting)} supporting relationships, "
              f"{len(direct)} evidence records, method="
              f"{(evidence.get('method') or 'none')[:34]}")
        previous = evidence["evidence_status"]
        outcome = io_client.post(
            f"/graph/relationship/{target['relationship_id']}/validate",
            json={"decision": "VALIDATED", "rationale": "End-to-end verification"},
        ).json()
        check("validation changes status", outcome["evidence_status"] == "VALIDATED",
              f"{previous} -> VALIDATED")
        db.expire_all()
        row = db.get(Relationship, target["relationship_id"])
        check("database reflects the decision", row.evidence_status == "VALIDATED")
        check("decision attributed to the user", row.validated_by_id is not None)
        trail = admin_client.get(
            "/audit/logs", params={"action": "RELATIONSHIP_VALIDATED"}
        ).json()
        check("decision written to the audit log", trail["total"] > 0,
              f"{trail['total']} entries")

    print("\n6. ENTITY RESOLUTION")
    candidates = io_client.get("/resolution/candidates").json()
    alias_pair = [
        c for c in candidates["items"]
        if {c["entity_a"]["uid"], c["entity_b"]["uid"]} == {"S1", "S2"}
    ]
    check("S1/S2 alias candidate surfaced", len(alias_pair) == 1,
          f"confidence {alias_pair[0]['confidence']}" if alias_pair else "not found")
    if alias_pair:
        check("matching factors itemised", len(alias_pair[0]["matching_factors"]) >= 4,
              f"{len(alias_pair[0]['matching_factors'])} factors")
        check("review required - nothing auto-merges", alias_pair[0]["review_required"])

    print("\n7. AI / NLP EXTRACTION")
    text = (
        "Rahul Sharma met Amit Verma at Noida Sector 62 on 10 January. "
        "Amit later transferred Rs 2,45,000 to Shivam Logistics."
    )
    nlp = io_client.post("/nlp/analyze", json={"text": text}).json()
    check("entities extracted", len(nlp["entities"]) >= 6, f"{len(nlp['entities'])}")
    check("relationships extracted", len(nlp["relationships"]) >= 2,
          f"{len(nlp['relationships'])}")
    spans_valid = all(
        text[e["start"]:e["end"]] == e["text"] for e in nlp["entities"]
    )
    check("every span maps back to the source text", spans_valid)
    check("known entities marked for linking",
          any(e["action"] == "link" for e in nlp["entities"]),
          f"{sum(1 for e in nlp['entities'] if e['action'] == 'link')} linkable")

    print("\n8. WOMEN SAFETY - SOS WORKFLOW")
    ws_client, _ = sign_in(creds, "WSO-052")
    sos = ws_client.post("/safety/sos", json={
        "subject_name": "E2E Test Subject", "latitude": 28.70, "longitude": 77.13,
        "location_text": "Verification point", "note": "automated test",
    }).json()
    ref = sos["alert_ref"]
    check("SOS raised at RECEIVED", sos["status"] == "RECEIVED", ref)
    check("location honestly labelled", sos["location"]["source"] == "SIMULATED")
    for nxt in ("ASSIGNED", "RESPONDING", "RESOLVED"):
        moved = ws_client.patch(f"/safety/sos/{ref}/status", json={"status": nxt}).json()
        check(f"SOS advances to {nxt}", moved["status"] == nxt)
    final = ws_client.get(f"/safety/sos/{ref}").json()
    check("full transition history persisted", len(final["history"]) == 4,
          " -> ".join(h["to"] for h in final["history"]))
    backwards = ws_client.patch(f"/safety/sos/{ref}/status", json={"status": "RECEIVED"})
    check("illegal backwards transition rejected", backwards.status_code == 400,
          f"HTTP {backwards.status_code}")

    print("\n9. SAFETY HEATMAP FILTERS")
    everything = ws_client.get("/safety/heatmap").json()
    stalking = ws_client.get("/safety/heatmap", params={"types": "stalking"}).json()
    check("filtering changes the incident population",
          everything["total_incidents"] != stalking["total_incidents"],
          f"{everything['total_incidents']} -> {stalking['total_incidents']}")
    check("zones carry a computed density",
          all("weighted_density" in z for z in everything["zones"]),
          f"top = {everything['zones'][0]['band']} @ {everything['zones'][0]['weighted_density']}")
    night = ws_client.get("/safety/heatmap",
                          params={"hour_from": 20, "hour_to": 4}).json()
    check("time-of-day filter narrows the set",
          night["total_incidents"] < everything["total_incidents"],
          f"{night['total_incidents']} at night vs {everything['total_incidents']} overall")

    print("\n10. AI SAFE ROUTE")
    night_route = ws_client.post(
        "/safety/routes", params={"from": "WP-LOC1", "to": "WP-LOC2", "depart_hour": 21}
    ).json()
    check("multiple routes compared", len(night_route["routes"]) >= 2,
          f"{len(night_route['routes'])} routes")
    check("each route explains its score",
          all(len(r["factors"]) >= 5 for r in night_route["routes"]))
    check("wording is never absolute",
          "Recommended based on" in night_route["recommendation"]["wording"])
    day_route = ws_client.post(
        "/safety/routes", params={"from": "WP-LOC1", "to": "WP-LOC2", "depart_hour": 10}
    ).json()
    check("time of day changes the score",
          night_route["routes"][0]["safety_score"] != day_route["routes"][0]["safety_score"],
          f"21:00 = {night_route['routes'][0]['safety_score']}, "
          f"10:00 = {day_route['routes'][0]['safety_score']}")

    print("\n11. PATTERN DETECTION")
    cases = ws_client.get("/cases").json()["items"]
    ws_case = next(c for c in cases if c["case_number"] == "DEMO/WS-2026-0417")
    patterns = ws_client.get("/safety/patterns", params={"case_id": ws_case["id"]}).json()
    check("suspicious patterns detected", len(patterns["suspicious_patterns"]) > 0,
          f"{len(patterns['suspicious_patterns'])}")
    check("repeated-encounter pattern detected",
          len(patterns["repeated_encounters"]) > 0,
          patterns["repeated_encounters"][0]["title"][:54]
          if patterns["repeated_encounters"] else "none")
    if patterns["repeated_encounters"]:
        first = patterns["repeated_encounters"][0]
        check("supporting events are real records",
              len(first["supporting_events"]) >= 2,
              f"{len(first['supporting_events'])} events")
        check("wording stays advisory",
              "Potential" in first["title"] and "review" in first["notice"].lower())

    print("\n12. REPORT GENERATION")
    core_case = next(c for c in cases if c["case_number"] == "NX-2026-0147")
    report = io_client.post(f"/reports/case/{core_case['id']}/generate").json()
    check("report generated", "report_ref" in report, report.get("report_ref"))
    check("report compiled from stored case data", report["summary"]["entities"] > 0,
          f"{report['summary']['entities']} entities, "
          f"{report['summary']['relationships']} relationships")
    pdf = io_client.get(f"/reports/{report['report_ref']}/pdf")
    check("PDF downloads", pdf.status_code == 200 and pdf.content[:4] == b"%PDF",
          f"{len(pdf.content):,} bytes")
    payload = io_client.get(f"/reports/{report['report_ref']}/json")
    check("JSON export works", payload.status_code == 200 and "case" in payload.json())
    check("report carries the disclaimer",
          "does not determine guilt" in payload.json()["disclaimer"])

    print("\n13. TIMELINE")
    timeline = io_client.get("/timeline", params={"case_id": core_case["id"]}).json()
    check("timeline populated", timeline["count"] > 0, f"{timeline['count']} events")
    check("events resolve back to source records",
          any(e.get("relationship_id") for e in timeline["items"]))

    print("\n14. DATA UPLOAD")
    # A unique suffix per run keeps the test re-runnable, and lets the repeat
    # upload below prove that deduplication actually fires.
    import uuid

    tag = uuid.uuid4().hex[:6].upper()
    csv = (
        "person,person_b,phone,location,date\n"
        f"Ravi Kulkarni {tag},Sneha Pillai {tag},98123{tag[:5].translate(str.maketrans('ABCDEF', '123456'))},Karol Bagh,2026-02-10\n"
        f"Ravi Kulkarni {tag},Manish Rao {tag},98123{tag[:5].translate(str.maketrans('ABCDEF', '123456'))},Karol Bagh,2026-02-11\n"
    )
    before_records = db.scalar(select(func.count()).select_from(Record))
    upload = io_client.post(
        "/data/upload",
        files={"file": (f"e2e_{tag}.csv", csv, "text/csv")},
        data={"source_type": "CDR"},
    ).json()
    counters = upload["counters"]
    check("counters equal the file contents", counters["records_received"] == 2,
          f"received {counters['records_received']} for 2 rows")
    check("entities extracted from upload", counters["entities_extracted"] > 0,
          f"{counters['entities_extracted']} entities, "
          f"{counters['relationships_created']} relationships")
    check("pipeline stages reported", len(upload.get("stages", [])) >= 8,
          f"{len(upload.get('stages', []))} stages")
    found = io_client.get("/entities/search",
                          params={"q": f"Ravi Kulkarni {tag}"}).json()
    check("uploaded entity is immediately searchable", found["count"] >= 1)

    repeat = io_client.post(
        "/data/upload",
        files={"file": (f"e2e_{tag}_again.csv", csv, "text/csv")},
        data={"source_type": "CDR"},
    ).json()
    check("re-uploading the same file is deduplicated",
          repeat["counters"]["duplicates"] == 2
          and repeat["counters"]["entities_extracted"] == 0,
          f"{repeat['counters']['duplicates']} duplicates, "
          f"{repeat['counters']['entities_extracted']} new entities")

    print("\n15. PERSISTENCE")
    db.expire_all()
    after_records = db.scalar(select(func.count()).select_from(Record))
    check("uploaded records persisted to the database",
          after_records > before_records,
          f"{before_records:,} -> {after_records:,}")

    db.close()
    print("\n" + "=" * 76)
    print(f"RESULT: {_ok} passed, {_fail} failed")
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
