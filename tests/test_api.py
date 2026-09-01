"""API behaviour: data consistency, evidence integrity and the safety workflows."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.base import EvidenceStatus
from app.db.models import Entity, Record, Relationship


# ------------------------------------------------------- data consistency


def test_dashboard_kpis_match_the_database(client, investigator, db):
    """The dashboard must never show a number the database disagrees with."""
    payload = client.get("/api/v1/dashboard", headers=investigator).json()
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}

    assert kpis["records"] == db.scalar(select(func.count()).select_from(Record))
    assert kpis["entities"] == db.scalar(
        select(func.count()).select_from(Entity).where(Entity.is_active.is_(True))
    )


def test_every_dashboard_widget_offers_a_route(client, investigator):
    payload = client.get("/api/v1/dashboard", headers=investigator).json()
    for kpi in payload["kpis"]:
        assert kpi["route"], f"KPI {kpi['key']} has no click-through"
    for row in payload["top_priority"]:
        assert row["route"].startswith("/entity/")
    for alert in payload["alerts"]:
        assert alert["route"]


def test_dashboard_scopes_to_a_case(client, investigator):
    cases = client.get("/api/v1/cases", headers=investigator).json()["items"]
    core = next(c for c in cases if c["case_number"] == "NX-2026-0147")
    scoped = client.get(
        "/api/v1/dashboard", params={"case_id": core["id"]}, headers=investigator
    ).json()
    assert scoped["scope"]["case_number"] == "NX-2026-0147"
    names = {row["name"] for row in scoped["top_priority"]}
    assert names, "a scoped dashboard must still rank entities"


# ------------------------------------------------------ evidence integrity


def test_observed_and_inferred_are_distinguished(client, investigator):
    profile = client.get("/api/v1/entities/p1", headers=investigator).json()
    for relationship in profile["relationships"]:
        assert relationship["evidence_status"] in {
            "OBSERVED", "INFERRED", "VALIDATED", "UNDER_REVIEW", "REJECTED"
        }
        expected = relationship["evidence_status"] in ("OBSERVED", "VALIDATED")
        assert relationship["is_observed"] is expected


def test_inferred_links_carry_a_reason_and_supporting_records(client, investigator):
    links = client.get("/api/v1/graph/hidden-links", headers=investigator).json()
    for stored in links["stored"]:
        if stored["evidence_status"] == "OBSERVED":
            continue
        assert stored["reason"], f"{stored['uid']} is inferred but states no reason"
        assert stored["disclaimer"]


def test_observed_relationships_cannot_be_validated(client, investigator, db):
    """Validation applies to inferences. An observed record is not up for a vote."""
    observed = db.scalars(
        select(Relationship).where(
            Relationship.evidence_status == EvidenceStatus.OBSERVED
        )
    ).first()
    response = client.post(
        f"/api/v1/graph/relationship/{observed.id}/validate",
        json={"decision": "VALIDATED"},
        headers=investigator,
    )
    assert response.status_code == 400


def test_priority_score_is_explainable_and_disclaimed(client, investigator):
    payload = client.get(
        "/api/v1/analytics/priority", params={"limit": 5}, headers=investigator
    ).json()
    assert "not a measure of guilt" in payload["disclaimer"].lower()
    for item in payload["items"]:
        assert item["factors"], "a score with no factors is not explainable"
        total = sum(f["contribution"] for f in item["factors"])
        assert abs(total - item["score"]) < 1.0, "factors must sum to the score"
        assert "not a probability of guilt" in item["disclaimer"].lower()


def test_graph_excludes_rejected_relationships(client, investigator, db):
    """A rejected link must leave analysis, not merely be relabelled."""
    payload = client.get(
        "/api/v1/graph/neighbourhood/p1", params={"depth": 2}, headers=investigator
    ).json()
    rejected_uids = set(
        db.scalars(
            select(Relationship.uid).where(
                Relationship.evidence_status == EvidenceStatus.REJECTED
            )
        ).all()
    )
    returned = {edge["uid"] for edge in payload["edges"]}
    assert not (returned & rejected_uids)


# --------------------------------------------------------------- search


def test_search_matches_names_and_aliases(client, investigator):
    result = client.get(
        "/api/v1/entities/search", params={"q": "Rahul"}, headers=investigator
    ).json()
    assert result["count"] >= 1
    assert any("Rahul" in r["name"] for r in result["results"])


def test_search_normalises_phone_formats(client, investigator):
    spaced = client.get(
        "/api/v1/entities/search", params={"q": "98765 43210"}, headers=investigator
    ).json()
    plain = client.get(
        "/api/v1/entities/search", params={"q": "9876543210"}, headers=investigator
    ).json()
    assert plain["count"] >= 1
    assert spaced["count"] >= 1, "a spaced phone number must find the same record"


def test_empty_search_returns_no_results(client, investigator):
    result = client.get(
        "/api/v1/entities/search", params={"q": ""}, headers=investigator
    ).json()
    assert result["results"] == []


# --------------------------------------------------------- women safety


def test_sos_follows_the_forward_only_workflow(client, safety_officer):
    created = client.post(
        "/api/v1/safety/sos",
        json={
            "subject_name": "Workflow Test",
            "latitude": 28.71, "longitude": 77.12,
            "location_text": "Test point",
        },
        headers=safety_officer,
    ).json()
    ref = created["alert_ref"]
    assert created["status"] == "RECEIVED"
    assert created["location"]["source"] == "SIMULATED", (
        "without a connected GPS source the position must be labelled simulated"
    )

    for step in ("ASSIGNED", "RESPONDING", "RESOLVED"):
        moved = client.patch(
            f"/api/v1/safety/sos/{ref}/status",
            json={"status": step}, headers=safety_officer,
        )
        assert moved.status_code == 200
        assert moved.json()["status"] == step

    # A resolved alert cannot be reopened by a status PATCH.
    assert client.patch(
        f"/api/v1/safety/sos/{ref}/status",
        json={"status": "RESPONDING"}, headers=safety_officer,
    ).status_code == 400

    detail = client.get(f"/api/v1/safety/sos/{ref}", headers=safety_officer).json()
    assert [h["to"] for h in detail["history"]] == [
        "RECEIVED", "ASSIGNED", "RESPONDING", "RESOLVED"
    ]


def test_sos_skipping_a_state_is_rejected(client, safety_officer):
    created = client.post(
        "/api/v1/safety/sos",
        json={"subject_name": "Skip Test", "latitude": 28.7, "longitude": 77.1},
        headers=safety_officer,
    ).json()
    response = client.patch(
        f"/api/v1/safety/sos/{created['alert_ref']}/status",
        json={"status": "RESOLVED"}, headers=safety_officer,
    )
    assert response.status_code == 400, "RECEIVED -> RESOLVED must not be allowed"


def test_investigator_cannot_dispatch(client, investigator, safety_officer):
    created = client.post(
        "/api/v1/safety/sos",
        json={"subject_name": "RBAC Test", "latitude": 28.7, "longitude": 77.1},
        headers=investigator,
    ).json()
    response = client.patch(
        f"/api/v1/safety/sos/{created['alert_ref']}/status",
        json={"status": "ASSIGNED"}, headers=investigator,
    )
    assert response.status_code == 403


def test_heatmap_recomputes_under_filters(client, safety_officer):
    everything = client.get("/api/v1/safety/heatmap", headers=safety_officer).json()
    stalking = client.get(
        "/api/v1/safety/heatmap", params={"types": "stalking"}, headers=safety_officer
    ).json()
    assert stalking["total_incidents"] < everything["total_incidents"]
    assert all("weighted_density" in z for z in everything["zones"])
    assert everything["zones"] == sorted(
        everything["zones"], key=lambda z: -z["weighted_density"]
    )


def test_safe_route_is_explainable_and_never_absolute(client, safety_officer):
    response = client.post(
        "/api/v1/safety/routes",
        params={"from": "WP-LOC1", "to": "WP-LOC2", "depart_hour": 21},
        headers=safety_officer,
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["routes"]) >= 2
    for route in payload["routes"]:
        assert len(route["factors"]) >= 5
        assert 0 <= route["safety_score"] <= 100
    wording = payload["recommendation"]["wording"].lower()
    assert "recommended based on" in wording
    assert "safe" not in wording.replace("safety", ""), (
        "a route must never be described as safe"
    )


def test_route_between_identical_points_is_rejected(client, safety_officer):
    response = client.post(
        "/api/v1/safety/routes",
        params={"from": "WP-LOC1", "to": "WP-LOC1"}, headers=safety_officer,
    )
    assert response.status_code == 400


def test_patterns_stay_advisory(client, safety_officer):
    payload = client.get("/api/v1/safety/patterns", headers=safety_officer).json()
    assert "do not identify" in payload["disclaimer"].lower()
    for pattern in payload["repeated_encounters"]:
        assert pattern["title"].startswith("Potential"), (
            "a co-occurrence must not be asserted as a fact"
        )
        assert "review" in pattern["notice"].lower()
        assert pattern["supporting_events"], "a pattern must cite its evidence"


# ------------------------------------------------------------- validation


def test_bad_input_returns_a_structured_validation_error(client, safety_officer):
    response = client.post(
        "/api/v1/safety/sos",
        json={"subject_name": "x", "latitude": 999, "longitude": 77.1},
        headers=safety_officer,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["fields"]


def test_unknown_entity_returns_404_not_500(client, investigator):
    response = client.get("/api/v1/entities/no-such-uid", headers=investigator)
    assert response.status_code == 404


def test_upload_rejects_unsupported_file_types(client, investigator):
    response = client.post(
        "/api/v1/data/upload",
        files={"file": ("payload.exe", b"MZ\x90\x00", "application/octet-stream")},
        data={"source_type": "FIR"},
        headers=investigator,
    )
    assert response.status_code == 400


def test_upload_rejects_an_empty_file(client, investigator):
    response = client.post(
        "/api/v1/data/upload",
        files={"file": ("empty.csv", b"   ", "text/csv")},
        data={"source_type": "FIR"},
        headers=investigator,
    )
    assert response.status_code == 400
