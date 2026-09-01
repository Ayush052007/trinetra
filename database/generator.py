"""Deterministic synthetic background corpus.

Why this exists: the two named demo cases hold about 45 entities between them.
Centrality percentiles, community detection, incident density and priority
banding are all *relative* measures - computed over a 45-node graph they are
arithmetically valid but statistically meaningless. This generator produces a
labelled background population so those measures have something real to rank
against.

Two guarantees:

  * Deterministic. Seeded RNG, so the same seed always yields the identical
    corpus. Any figure the platform displays can be re-derived.
  * Labelled. Every row is written with data_classification = SYNTHETIC and is
    excluded from nothing - it is visibly synthetic wherever it surfaces.

The generator builds genuine community structure rather than uniform random
edges, because a graph with no communities would make community detection
look broken when it is in fact working correctly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

# Name pools. Ordinary Indian given names and surnames, combined at random;
# any resemblance to a specific person is coincidental and unintended.
GIVEN_NAMES = [
    "Aarav", "Aditya", "Ananya", "Ankit", "Anjali", "Arjun", "Asha", "Bhavna",
    "Chirag", "Deepa", "Dinesh", "Divya", "Farhan", "Gaurav", "Geeta", "Harsh",
    "Indira", "Ishaan", "Jaya", "Kabir", "Kavita", "Kiran", "Lakshmi", "Manish",
    "Meena", "Mohit", "Naina", "Nikhil", "Nisha", "Pankaj", "Pooja", "Rajesh",
    "Rakhi", "Ravi", "Rekha", "Rohit", "Sameer", "Sanya", "Shalini", "Shivam",
    "Sneha", "Sunil", "Tanvi", "Tarun", "Uma", "Varun", "Vidya", "Vinay",
    "Yash", "Zoya", "Aisha", "Bharat", "Charu", "Devika", "Girish", "Hema",
]

SURNAMES = [
    "Agarwal", "Bansal", "Bhatia", "Chauhan", "Chopra", "Desai", "Dutta",
    "Gupta", "Iyer", "Jain", "Joshi", "Kapoor", "Khanna", "Kulkarni", "Kumar",
    "Malhotra", "Mehta", "Menon", "Mishra", "Nair", "Pandey", "Patel", "Rao",
    "Reddy", "Saxena", "Sethi", "Shah", "Sharma", "Singh", "Sinha", "Thakur",
    "Trivedi", "Verma", "Yadav", "Bose", "Ghosh", "Pillai", "Rathore",
]

ORG_PREFIX = [
    "Apex", "Bharat", "Capital", "Deccan", "Eastern", "Frontier", "Ganga",
    "Horizon", "Indus", "Jyoti", "Kaveri", "Lotus", "Meridian", "Northstar",
    "Orbit", "Pinnacle", "Quantum", "Ridge", "Summit", "Trident", "Unity",
    "Vertex", "Westline", "Zenith",
]

ORG_SUFFIX = [
    "Logistics Pvt. Ltd.", "Trading Co.", "Freight Co.", "Finserv",
    "Enterprises", "Traders", "Holdings Pvt. Ltd.", "Exports Pvt. Ltd.",
    "Transport Co.", "Capital Services", "Agencies", "Industries Ltd.",
]

# Localities across the NCR. Coordinates are approximate area centroids
# (SYNTHETIC_GEO) - they anchor distance calculations, not real addresses.
LOCALITIES = [
    ("Rohini Sector 7", 28.7041, 77.1025),
    ("Pitampura", 28.6942, 77.1315),
    ("Karol Bagh", 28.6519, 77.1909),
    ("Dwarka Sector 12", 28.5921, 77.0460),
    ("Janakpuri", 28.6219, 77.0878),
    ("Saket", 28.5245, 77.2066),
    ("Lajpat Nagar", 28.5677, 77.2433),
    ("Mayur Vihar", 28.6127, 77.2954),
    ("Shahdara", 28.6692, 77.2887),
    ("Noida Sector 18", 28.5708, 77.3260),
    ("Noida Sector 62", 28.6270, 77.3620),
    ("Greater Noida", 28.4744, 77.5040),
    ("Gurugram Sector 29", 28.4595, 77.0266),
    ("Faridabad NIT", 28.4089, 77.3178),
    ("Ghaziabad Vaishali", 28.6692, 77.4538),
    ("Connaught Place, Delhi", 28.6315, 77.2167),
    ("Chandni Chowk", 28.6506, 77.2303),
    ("Nehru Place", 28.5494, 77.2506),
    ("Okhla Industrial Area", 28.5355, 77.2730),
    ("Azadpur", 28.7076, 77.1750),
]

VEHICLE_SERIES = ["DL", "HR", "UP", "RJ", "PB"]

TXN_TYPES = ["NEFT", "RTGS", "UPI", "IMPS", "CASH", "CHEQUE"]

SOURCE_TYPES = ["FIR", "CDR", "Financial", "Surveillance", "Records", "Social Media"]

# Relationship vocabulary, restricted to pairs that make sense by type.
TYPED_RELATIONS: dict[tuple[str, str], list[str]] = {
    ("person", "person"): ["CALLED", "MET", "ASSOCIATED_WITH"],
    ("person", "phone"): ["OWNED"],
    ("person", "location"): ["VISITED", "resides_at"],
    ("person", "organization"): ["WORKED_FOR", "ASSOCIATED_WITH"],
    ("person", "vehicle"): ["OWNED"],
    ("person", "transaction"): ["TRANSFERRED_MONEY"],
    ("transaction", "organization"): ["ASSOCIATED_WITH"],
    ("vehicle", "location"): ["sighted_at"],
    ("organization", "location"): ["ASSOCIATED_WITH"],
}


@dataclass
class GeneratedEntity:
    uid: str
    type: str
    name: str
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    latitude: float | None = None
    longitude: float | None = None
    community: int = 0


@dataclass
class GeneratedRelationship:
    source_uid: str
    target_uid: str
    type: str
    source_ref: str
    occurred_at: datetime
    confidence: float
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedRecord:
    source_type: str
    source_ref: str
    occurred_at: datetime
    payload: dict[str, Any]


@dataclass
class Corpus:
    entities: list[GeneratedEntity] = field(default_factory=list)
    relationships: list[GeneratedRelationship] = field(default_factory=list)
    records: list[GeneratedRecord] = field(default_factory=list)
    incidents: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        by_type: dict[str, int] = {}
        for e in self.entities:
            by_type[e.type] = by_type.get(e.type, 0) + 1
        return {
            "entities": len(self.entities),
            "relationships": len(self.relationships),
            "records": len(self.records),
            "incidents": len(self.incidents),
            **{f"entities_{k}": v for k, v in sorted(by_type.items())},
        }


class CorpusGenerator:
    """Builds a labelled synthetic population with realistic structure."""

    VERSION = "corpus-1.0"

    def __init__(
        self,
        seed: int = 26189,           # the SIH problem statement number
        people: int = 900,
        communities: int = 18,
        base_date: datetime | None = None,
    ) -> None:
        self.rng = random.Random(seed)
        self.seed = seed
        self.people = people
        self.communities = communities
        self.base_date = base_date or datetime(2025, 10, 1, tzinfo=UTC)
        self._counter = 0

    def _uid(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-g{self._counter:05d}"

    def _date(self, day_spread: int = 330) -> datetime:
        return self.base_date + timedelta(
            days=self.rng.randint(0, day_spread),
            hours=self.rng.randint(0, 23),
            minutes=self.rng.randint(0, 59),
        )

    # -- entity construction ---------------------------------------------

    def _make_person(self, community: int) -> GeneratedEntity:
        given = self.rng.choice(GIVEN_NAMES)
        surname = self.rng.choice(SURNAMES)
        name = f"{given} {surname}"
        aliases: list[str] = []
        # A minority of records carry a redacted or short form, which is what
        # gives entity resolution genuine work to do.
        roll = self.rng.random()
        if roll < 0.09:
            aliases.append(f"{given[0]}. {surname}")
        elif roll < 0.14:
            aliases.append(f"{given} {surname[0]}.")
        return GeneratedEntity(
            uid=self._uid("p"),
            type="person",
            name=name,
            aliases=aliases,
            attributes={"occupation": self.rng.choice([
                "Driver", "Clerk", "Trader", "Accountant", "Freight Operator",
                "Shopkeeper", "Contractor", "Agent", "Technician", "Unknown",
            ])},
            community=community,
        )

    def _make_phone(self, community: int) -> GeneratedEntity:
        number = f"{self.rng.choice('6789')}{self.rng.randint(100000000, 999999999)}"
        return GeneratedEntity(
            uid=self._uid("ph"),
            type="phone",
            name=number,
            attributes={
                "carrier": self.rng.choice(["Demo Telecom", "Demo Cellular", "Demo Mobile"]),
                "registered": self.rng.random() > 0.18,
            },
            community=community,
        )

    def _make_vehicle(self, community: int) -> GeneratedEntity:
        reg = (
            f"{self.rng.choice(VEHICLE_SERIES)} {self.rng.randint(1, 99):02d} "
            f"{self.rng.choice('ABCDEFGHJK')}{self.rng.choice('ABCDEFGHJK')} "
            f"{self.rng.randint(1000, 9999)}"
        )
        return GeneratedEntity(
            uid=self._uid("v"),
            type="vehicle",
            name=reg,
            attributes={"model": self.rng.choice(
                ["Sedan", "Hatchback", "SUV", "Two-wheeler", "Van", "Light Truck"]
            )},
            community=community,
        )

    def _make_org(self, community: int) -> GeneratedEntity:
        name = f"{self.rng.choice(ORG_PREFIX)} {self.rng.choice(ORG_SUFFIX)}"
        return GeneratedEntity(
            uid=self._uid("o"),
            type="organization",
            name=name,
            attributes={"sector": self.rng.choice(
                ["Logistics", "Trading", "Finance", "Transport", "Export", "Retail"]
            )},
            community=community,
        )

    def _make_transaction(self, community: int) -> GeneratedEntity:
        amount = self.rng.choice([
            self.rng.randrange(5_000, 50_000, 1_000),
            self.rng.randrange(50_000, 500_000, 5_000),
            self.rng.randrange(500_000, 2_500_000, 25_000),
        ])
        return GeneratedEntity(
            uid=self._uid("t"),
            type="transaction",
            name=f"Rs {amount:,}",
            attributes={"amount": amount, "txn_type": self.rng.choice(TXN_TYPES)},
            community=community,
        )

    # -- main build ------------------------------------------------------

    def generate(self) -> Corpus:
        corpus = Corpus()

        # Locations are shared across communities - geography is common ground.
        location_entities: list[GeneratedEntity] = []
        for name, lat, lng in LOCALITIES:
            location_entities.append(
                GeneratedEntity(
                    uid=self._uid("l"),
                    type="location",
                    name=name,
                    latitude=lat,
                    longitude=lng,
                    community=-1,
                )
            )
        corpus.entities.extend(location_entities)

        # Build each community as a loosely-connected cluster.
        community_members: dict[int, list[GeneratedEntity]] = {}
        for community in range(self.communities):
            members: list[GeneratedEntity] = []
            size = self.rng.randint(
                max(6, self.people // (self.communities * 2)),
                max(10, (self.people * 2) // self.communities),
            )
            people = [self._make_person(community) for _ in range(size)]
            members.extend(people)
            members.extend(
                self._make_phone(community) for _ in range(int(size * 0.85))
            )
            members.extend(self._make_vehicle(community) for _ in range(max(1, size // 4)))
            members.extend(self._make_org(community) for _ in range(max(1, size // 6)))
            members.extend(self._make_transaction(community) for _ in range(max(1, size // 3)))
            community_members[community] = members
            corpus.entities.extend(members)

        # Each community operates in its own two-to-four home localities.
        # Letting every cluster touch all twenty would turn locations into
        # global hubs that connect everything to everything, which destroys
        # the community structure and makes betweenness meaningless.
        home_localities: dict[int, list[GeneratedEntity]] = {
            community: self.rng.sample(location_entities, self.rng.randint(2, 4))
            for community in range(self.communities)
        }

        # Intra-community relationships: dense, meaningful, typed.
        for community, members in community_members.items():
            local_locations = home_localities[community]
            by_type: dict[str, list[GeneratedEntity]] = {}
            for m in members:
                by_type.setdefault(m.type, []).append(m)

            people = by_type.get("person", [])
            phones = by_type.get("phone", [])
            vehicles = by_type.get("vehicle", [])
            orgs = by_type.get("organization", [])
            transactions = by_type.get("transaction", [])

            # Give most people a phone; some share one (investigatively useful).
            for i, person in enumerate(people):
                if i < len(phones):
                    corpus.relationships.append(
                        self._relationship(person, phones[i], "OWNED", "Telecom KYC", 1.0)
                    )
            # Person-to-person contact within the cluster.
            for person in people:
                contacts = self.rng.sample(
                    people, min(len(people), self.rng.randint(1, 4))
                )
                for other in contacts:
                    if other.uid == person.uid:
                        continue
                    rel_type = self.rng.choice(TYPED_RELATIONS[("person", "person")])
                    attrs = {}
                    if rel_type == "CALLED":
                        attrs["call_count"] = self.rng.randint(1, 40)
                    corpus.relationships.append(
                        self._relationship(
                            person, other, rel_type,
                            f"CDR-{person.uid}" if rel_type == "CALLED"
                            else f"Surveillance Report SR-{self.rng.randint(200, 999)}",
                            round(self.rng.uniform(0.45, 0.97), 2),
                            attrs,
                        )
                    )
            # Employment and vehicles.
            for person in people:
                if orgs and self.rng.random() < 0.55:
                    corpus.relationships.append(
                        self._relationship(
                            person, self.rng.choice(orgs), "WORKED_FOR",
                            f"Employment Record ER-{self.rng.randint(100, 999)}",
                            round(self.rng.uniform(0.7, 0.95), 2),
                        )
                    )
                if vehicles and self.rng.random() < 0.30:
                    corpus.relationships.append(
                        self._relationship(
                            person, self.rng.choice(vehicles), "OWNED",
                            f"Vehicle Registration RC-{self.rng.randint(1000, 9999)}",
                            round(self.rng.uniform(0.8, 0.98), 2),
                        )
                    )
                # Movement, within the community's home localities.
                for location in self.rng.sample(
                    local_locations, min(len(local_locations), self.rng.randint(1, 3))
                ):
                    corpus.relationships.append(
                        self._relationship(
                            person, location, "VISITED",
                            f"Surveillance Report SR-{self.rng.randint(200, 999)}",
                            round(self.rng.uniform(0.4, 0.9), 2),
                            {"visit_count": self.rng.randint(1, 9)},
                        )
                    )
            # Money movement: person -> amount -> organisation.
            for txn in transactions:
                if not people or not orgs:
                    continue
                payer = self.rng.choice(people)
                payee = self.rng.choice(orgs)
                ref = f"Bank Statement BS-{self.rng.randint(1000, 9999)}"
                corpus.relationships.append(
                    self._relationship(payer, txn, "TRANSFERRED_MONEY", ref,
                                       round(self.rng.uniform(0.8, 0.99), 2),
                                       {"amount": txn.attributes.get("amount")})
                )
                corpus.relationships.append(
                    self._relationship(txn, payee, "ASSOCIATED_WITH", ref,
                                       round(self.rng.uniform(0.8, 0.99), 2))
                )
            # Vehicle sightings.
            for vehicle in vehicles:
                for location in self.rng.sample(
                    local_locations, min(len(local_locations), self.rng.randint(1, 3))
                ):
                    corpus.relationships.append(
                        self._relationship(
                            vehicle, location, "sighted_at",
                            f"Surveillance Report SR-{self.rng.randint(200, 999)}",
                            round(self.rng.uniform(0.5, 0.95), 2),
                        )
                    )

        # Sparse inter-community bridges. These are what make betweenness
        # centrality and hidden-link discovery meaningful: a handful of people
        # who connect otherwise separate clusters.
        all_people = [e for e in corpus.entities if e.type == "person" and e.community >= 0]
        bridge_count = max(8, self.communities * 2)
        for _ in range(bridge_count):
            a, b = self.rng.sample(all_people, 2)
            if a.community == b.community:
                continue
            corpus.relationships.append(
                self._relationship(
                    a, b, self.rng.choice(["CALLED", "MET", "ASSOCIATED_WITH"]),
                    f"CDR-BRIDGE-{self.rng.randint(100, 999)}",
                    round(self.rng.uniform(0.5, 0.85), 2),
                    {"call_count": self.rng.randint(1, 12)},
                )
            )

        corpus.records = self._records_from(corpus.relationships)
        corpus.incidents = self._incidents(location_entities)
        return corpus

    def _relationship(
        self,
        source: GeneratedEntity,
        target: GeneratedEntity,
        rel_type: str,
        source_ref: str,
        confidence: float,
        attributes: dict[str, Any] | None = None,
    ) -> GeneratedRelationship:
        return GeneratedRelationship(
            source_uid=source.uid,
            target_uid=target.uid,
            type=rel_type,
            source_ref=source_ref,
            occurred_at=self._date(),
            confidence=confidence,
            attributes=attributes or {},
        )

    def _records_from(self, relationships: list[GeneratedRelationship]) -> list[GeneratedRecord]:
        """One raw record per relationship, mirroring how ingestion produces them.

        This is what makes 'Total Records' a countable fact rather than a
        decorative number.
        """
        records: list[GeneratedRecord] = []
        for rel in relationships:
            ref = rel.source_ref
            source_type = (
                "FIR" if ref.startswith("FIR")
                else "CDR" if ref.startswith("CDR")
                else "Financial" if "Bank" in ref
                else "Surveillance" if "Surveillance" in ref
                else "Records"
            )
            records.append(
                GeneratedRecord(
                    source_type=source_type,
                    source_ref=ref,
                    occurred_at=rel.occurred_at,
                    payload={
                        "source": rel.source_uid,
                        "target": rel.target_uid,
                        "relationship": rel.type,
                        "confidence": rel.confidence,
                        **rel.attributes,
                    },
                )
            )
        return records

    def _incidents(self, locations: list[GeneratedEntity]) -> list[dict[str, Any]]:
        """Background safety incidents, so heatmap density is a real measure.

        Distribution is deliberately uneven across localities and hours -
        a uniform scatter would render every zone the same colour and make the
        filters look broken.
        """
        types = [
            ("harassment", 0.30), ("stalking", 0.18), ("suspicious_contact", 0.16),
            ("threat", 0.12), ("suspicious_vehicle", 0.10),
            ("assault_or_confrontation", 0.08), ("missing_person", 0.03), ("other", 0.03),
        ]
        weights = [w for _, w in types]
        names = [t for t, _ in types]

        # Some localities carry markedly more reports than others.
        hotspots = self.rng.sample(locations, max(3, len(locations) // 4))
        incidents: list[dict[str, Any]] = []
        for i in range(420):
            if self.rng.random() < 0.55 and hotspots:
                location = self.rng.choice(hotspots)
            else:
                location = self.rng.choice(locations)
            incident_type = self.rng.choices(names, weights=weights, k=1)[0]
            # Evening and night hours are over-represented, as in reporting data.
            hour = self.rng.choices(
                list(range(24)),
                weights=[2, 1, 1, 1, 1, 2, 3, 4, 5, 5, 5, 5, 5, 5, 5, 6, 7, 9, 11, 12, 11, 8, 5, 3],
                k=1,
            )[0]
            occurred = self._date() .replace(hour=hour)
            severity = self.rng.choices(
                ["LOW", "MEDIUM", "HIGH", "CRITICAL"], weights=[0.30, 0.42, 0.22, 0.06], k=1
            )[0]
            incidents.append({
                "incident_ref": f"WSI-G{i + 1:04d}",
                "type": incident_type,
                "priority": severity,
                "status": self.rng.choice(["open", "investigating", "review", "closed"]),
                "occurred_at": occurred,
                "hour_of_day": hour,
                "location_uid": location.uid,
                "latitude": location.latitude + self.rng.uniform(-0.012, 0.012),
                "longitude": location.longitude + self.rng.uniform(-0.012, 0.012),
                "location_text": location.name,
                "description": (
                    f"Synthetic background report of {incident_type.replace('_', ' ')} "
                    f"near {location.name}."
                ),
            })
        return incidents
