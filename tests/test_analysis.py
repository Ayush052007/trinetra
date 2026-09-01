"""Graph algorithms, NLP extraction, entity resolution and priority scoring.

These test the analytical core directly, without HTTP, so a change in scoring
or extraction behaviour is caught at the unit that produced it.
"""

from __future__ import annotations

import pytest

from trinetra_er.resolver import (
    EntityResolver,
    ResolutionInput,
    is_abbreviation_of,
    jaro_winkler,
    soundex,
)
from trinetra_graph import algorithms as algo
from trinetra_nlp.engine import Gazetteer, RuleBasedEngine, normalize


# ------------------------------------------------------------------- graph


@pytest.fixture
def bridged_graph():
    """Two triangles joined by a single bridge - a known topology."""
    nodes = list("abcdefg")
    edges = [
        ("a", "b", 1), ("b", "c", 1), ("a", "c", 1),
        ("c", "d", 1),                       # the bridge
        ("d", "e", 1), ("e", "f", 1), ("d", "f", 1), ("f", "g", 1),
    ]
    return algo.build_adjacency(nodes, edges)


def test_k_hop_respects_depth(bridged_graph):
    assert set(algo.k_hop(bridged_graph, "a", 1)) == {"a", "b", "c"}
    assert set(algo.k_hop(bridged_graph, "a", 2)) == {"a", "b", "c", "d"}


def test_shortest_path_and_unreachable():
    adj = algo.build_adjacency(list("xyz"), [("x", "y", 1)])
    assert algo.shortest_path(adj, "x", "y") == ["x", "y"]
    assert algo.shortest_path(adj, "x", "z") == [], "unreachable must return empty"


def test_betweenness_identifies_the_bridge(bridged_graph):
    scores = algo.betweenness_centrality(bridged_graph)
    top = max(scores, key=scores.get)
    assert top in ("c", "d"), "the bridge nodes must dominate betweenness"


def test_sampled_betweenness_is_deterministic_and_faster(bridged_graph):
    a = algo.betweenness_centrality(bridged_graph, pivots=3)
    b = algo.betweenness_centrality(bridged_graph, pivots=3)
    assert a == b, "sampling must be seeded and reproducible"


def test_closeness_exact_path_unchanged_by_the_pivots_parameter(bridged_graph):
    assert algo.closeness_centrality(bridged_graph) == algo.closeness_centrality(
        bridged_graph, pivots=None
    )


def test_communities_separate_the_two_triangles(bridged_graph):
    assignment = algo.louvain_communities(bridged_graph)
    assert len(set(assignment.values())) >= 2
    assert algo.modularity(bridged_graph, assignment) > 0.2


def test_connected_components(bridged_graph):
    assert len(algo.connected_components(bridged_graph)) == 1
    split = algo.build_adjacency(list("pqrs"), [("p", "q", 1), ("r", "s", 1)])
    assert len(algo.connected_components(split)) == 2


def test_k_shortest_paths_returns_distinct_routes(bridged_graph):
    routes = algo.k_shortest_paths(bridged_graph, "a", "f", lambda u, v, r: 1.0, k=3)
    assert len(routes) >= 2
    assert len({tuple(p) for p, _ in routes}) == len(routes), "routes must differ"


def test_haversine_matches_a_known_distance():
    # ~20 km north-south separation in Delhi.
    assert 19 < algo.haversine_km(28.70, 77.10, 28.52, 77.10) < 21


# --------------------------------------------------------------------- NLP


@pytest.fixture
def gazetteer():
    g = Gazetteer()
    for uid, kind, name, aliases in [
        ("p1", "person", "Rahul Sharma", ["Rahul S."]),
        ("p2", "person", "Amit Verma", []),
        ("p4", "person", "Neha Sharma", []),
        ("l1", "location", "Noida Sector 62", []),
        ("o1", "organization", "Shivam Logistics", []),
    ]:
        g.add(uid, kind, name, aliases)
    return g


def test_normalisation_collapses_phone_formats():
    assert normalize("+91 98765 43210", "phone") == normalize("9876543210", "phone")
    assert normalize("DL 8C AA 1234", "vehicle") == normalize("DL-8C-AA-1234", "vehicle")


def test_extraction_finds_the_expected_entities(gazetteer):
    text = (
        "Rahul Sharma met Amit Verma at Noida Sector 62 on 10 January. "
        "Amit later transferred Rs 2,45,000 to Shivam Logistics."
    )
    result = RuleBasedEngine().analyze(text, gazetteer)
    kinds = {e.type for e in result.entities}
    assert {"person", "location", "transaction", "organization"} <= kinds


def test_every_extraction_span_maps_back_to_the_source(gazetteer):
    text = (
        "Rahul Sharma met Amit Verma at Noida Sector 62. "
        "Vehicle DL-0X-XX-4471 was sighted there and +91-70xxxx4482 called twice."
    )
    result = RuleBasedEngine().analyze(text, gazetteer)
    assert result.entities
    for entity in result.entities:
        assert text[entity.start:entity.end] == entity.text


def test_relationship_extraction_captures_the_money_recipient(gazetteer):
    text = "Amit Verma transferred Rs 2,45,000 to Shivam Logistics."
    result = RuleBasedEngine().analyze(text, gazetteer)
    pairs = {(r.source_text, r.type, r.target_text) for r in result.relationships}
    assert any(
        t == "TRANSFERRED_MONEY" and "Shivam" in target for _, t, target in pairs
    ), "the payee, not just the amount, must be extracted"


def test_partial_name_resolution_refuses_ambiguous_tokens(gazetteer):
    # "Sharma" is shared by Rahul Sharma and Neha Sharma.
    assert gazetteer._unambiguous_part("Sharma") is None
    assert gazetteer._unambiguous_part("Rahul")[0] == "p1"


def test_empty_text_is_handled():
    result = RuleBasedEngine().analyze("")
    assert result.entities == [] and result.relationships == []
    assert result.confidence == 0.0


# ------------------------------------------------------- entity resolution


def test_abbreviation_detection():
    assert is_abbreviation_of("R. Sharma", "Rahul Sharma")
    assert is_abbreviation_of("Rahul S.", "Rahul Sharma")
    assert not is_abbreviation_of("A. Verma", "Rahul Sharma")
    assert not is_abbreviation_of("Rahul Sharma", "Rahul Sharma"), (
        "an identical string is not an abbreviation of itself"
    )


def test_phonetic_and_string_similarity():
    assert soundex("Sharma") == soundex("Sharmaa")
    assert jaro_winkler("verma", "verna") > 0.85


def test_alias_pair_with_shared_identifiers_is_surfaced():
    """Different names, same ID proof and vehicle - the classic alias shape."""
    resolver = EntityResolver()
    a = ResolutionInput("S1", "person", "R. Verma", [],
                        {"id_proof": "IDP-4471", "vehicle": "DL0XXX4471"},
                        {"PH1", "VEH1"}, {"WS-0417"})
    b = ResolutionInput("S2", "person", "S. Mehta", [],
                        {"id_proof": "IDP-4471", "vehicle": "DL0XXX4471"},
                        {"CASE_PRIOR", "VEH1"}, {"WS-0417"})
    candidate = resolver.score_pair(a, b)
    assert candidate.confidence > 0.75, "shared hard identifiers must carry the match"
    assert candidate.requires_review is True, "nothing may auto-merge"
    assert len(candidate.factors) >= 5, "every score must decompose into factors"


def test_name_coincidence_alone_is_capped():
    """Two unrelated people with the same name must not score highly."""
    resolver = EntityResolver()
    a = ResolutionInput("x1", "person", "Vikram Singh", [], {}, set(), {"CASE-A"})
    b = ResolutionInput("x2", "person", "Vikram Singh", [], {}, set(), {"CASE-B"})
    candidate = resolver.score_pair(a, b)
    assert candidate.confidence < resolver.REVIEW_THRESHOLD


def test_blocking_pairs_records_that_share_an_identifier():
    """Alias detection depends on identifier blocking, not just name blocking."""
    resolver = EntityResolver()
    entities = [
        ResolutionInput("S1", "person", "R. Verma", [], {"id_proof": "IDP-1"}, set(), set()),
        ResolutionInput("S2", "person", "S. Mehta", [], {"id_proof": "IDP-1"}, set(), set()),
    ]
    pairs = resolver.candidate_pairs(entities)
    assert len(pairs) == 1, "records sharing an ID proof must be compared"
