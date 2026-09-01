"""Literal seed data, transcribed from the project material.

Provenance for every block is stated inline. Nothing here is invented beyond
what the source documents contain, except geographic coordinates, which the
source data does not carry and which the heatmap and routing engine require -
those are marked SYNTHETIC_GEO and are approximate points in the stated
localities, not real addresses.
"""

from __future__ import annotations

# ===========================================================================
# DEPARTMENT ROSTER
# ---------------------------------------------------------------------------
# Roles are the five in docs/reference/REQUIREMENTS.md section 23, mapped to
# the designations shown on the sign-in screen of the original prototype.
# Names are fictional placeholders for a deploying unit's real staff list.
# Passwords are NOT stored here - they are generated at seed time and written
# to a gitignored CREDENTIALS.md.
# ===========================================================================

DEPARTMENT_ROSTER = [
    {
        "service_id": "IO-114",
        "full_name": "Arjun Deshmukh",
        "role": "INVESTIGATOR",
        "designation": "Investigating Officer",
        "unit": "Criminal Network Intelligence Unit",
        "email": "io114@trinetra.local",
        "extension": "2114",
    },
    {
        "service_id": "SI-207",
        "full_name": "Meera Raghunathan",
        "role": "SENIOR_INVESTIGATOR",
        "designation": "Supervisory Officer",
        "unit": "Criminal Network Intelligence Unit",
        "email": "si207@trinetra.local",
        "extension": "2207",
    },
    {
        "service_id": "AN-331",
        "full_name": "Kabir Anand",
        "role": "ANALYST",
        "designation": "Intelligence Analyst",
        "unit": "Data Analysis Cell",
        "email": "an331@trinetra.local",
        "extension": "2331",
    },
    {
        "service_id": "WSO-052",
        "full_name": "Farida Qureshi",
        "role": "WOMEN_SAFETY_OFFICER",
        "designation": "Women Safety Officer",
        "unit": "Women Safety Division",
        "email": "wso052@trinetra.local",
        "extension": "2052",
    },
    {
        "service_id": "CFI-188",
        "full_name": "Nikhil Bose",
        "role": "ANALYST",
        "designation": "Cyber & Financial Investigator",
        "unit": "Cyber & Financial Crimes Cell",
        "email": "cfi188@trinetra.local",
        "extension": "2188",
    },
    {
        "service_id": "ADM-001",
        "full_name": "Sunita Iyer",
        "role": "ADMIN",
        "designation": "NCRB Administrator",
        "unit": "System Administration",
        "email": "adm001@trinetra.local",
        "extension": "2001",
    },
]


# ===========================================================================
# GEOGRAPHY  (SYNTHETIC_GEO)
# ---------------------------------------------------------------------------
# The source data names localities but carries no coordinates. These are
# approximate centroids of the named areas, used so density, routing and
# proximity are computed on real distances rather than invented numbers.
# They do not correspond to any real address, person or incident.
# ===========================================================================

LOCATION_COORDS = {
    # Women Safety case - north-west Delhi
    "LOC1": (28.7196, 77.1025, "Victim Residence (NW Delhi)"),
    "LOC2": (28.6950, 77.1400, "Victim Workplace"),
    "LOC3": (28.7080, 77.1230, "Confrontation Site"),
    # Financial network case
    "l1": (28.6270, 77.3620, "Noida Sector 62"),
    "l2": (28.6315, 77.2167, "Delhi"),
    "l3": (28.6315, 77.2167, "Connaught Place, Delhi"),
    "l4": (28.4595, 77.0266, "Gurugram"),
    "l5": (28.6692, 77.4538, "Ghaziabad"),
}

# Zones from the source JSON safety_zones block, given centroids.
SAFETY_ZONES = [
    {
        "zone_ref": "ZONE-01",
        "name": "NW Delhi Residential Belt",
        "description": "Residential locality including LOC1",
        "center_lat": 28.7196,
        "center_lng": 77.1025,
        "radius_km": 1.6,
    },
    {
        "zone_ref": "ZONE-02",
        "name": "Workplace Corridor",
        "description": "Commercial corridor including LOC2",
        "center_lat": 28.6950,
        "center_lng": 77.1400,
        "radius_km": 1.4,
    },
    {
        "zone_ref": "ZONE-03",
        "name": "Confrontation Site Sector",
        "description": "Area surrounding LOC3",
        "center_lat": 28.7080,
        "center_lng": 77.1230,
        "radius_km": 1.2,
    },
    {
        "zone_ref": "ZONE-04",
        "name": "Central Market",
        "description": "Market area - fictional demonstration zone",
        "center_lat": 28.6890,
        "center_lng": 77.1180,
        "radius_km": 1.3,
    },
    {
        "zone_ref": "ZONE-05",
        "name": "Sector 4",
        "description": "Mixed-use sector - fictional demonstration zone",
        "center_lat": 28.7300,
        "center_lng": 77.1320,
        "radius_km": 1.5,
    },
]

# From the source JSON emergency_services block.
EMERGENCY_SERVICES = [
    {
        "service_ref": "ES-001",
        "type": "Police Station",
        "name": "Demo Police Station North-West",
        "zone_ref": "ZONE-01",
        "latitude": 28.7170,
        "longitude": 77.1080,
        "status": "AVAILABLE",
        "contact": "100",
    },
    {
        "service_ref": "ES-002",
        "type": "Hospital",
        "name": "Demo General Hospital",
        "zone_ref": "ZONE-02",
        "latitude": 28.6975,
        "longitude": 77.1365,
        "status": "AVAILABLE",
        "contact": "102",
    },
    {
        "service_ref": "ES-003",
        "type": "Emergency Response Unit",
        "name": "Demo Women Safety Response Unit",
        "zone_ref": "ZONE-03",
        "latitude": 28.7060,
        "longitude": 77.1265,
        "status": "AVAILABLE",
        "contact": "1091",
    },
    {
        "service_ref": "ES-004",
        "type": "Safe/Public Location",
        "name": "Demo Community Help Centre",
        "zone_ref": "ZONE-04",
        "latitude": 28.6905,
        "longitude": 77.1205,
        "status": "OPEN",
        "contact": "1091",
    },
    {
        "service_ref": "ES-005",
        "type": "Police Station",
        "name": "Demo Police Station Sector 4",
        "zone_ref": "ZONE-05",
        "latitude": 28.7288,
        "longitude": 77.1290,
        "status": "AVAILABLE",
        "contact": "100",
    },
    {
        "service_ref": "ES-006",
        "type": "Hospital",
        "name": "Demo Trauma Centre West",
        "zone_ref": "ZONE-04",
        "latitude": 28.6862,
        "longitude": 77.1150,
        "status": "AVAILABLE",
        "contact": "102",
    },
]


# ===========================================================================
# CASE NX-2026-0147 - Financial Network Investigation
# ---------------------------------------------------------------------------
# Transcribed from legacy-prototype/js/data.js, which is the project's own
# synthetic dataset for this case. All names, numbers and organisations are
# fictional.
# ===========================================================================

CORE_ENTITIES = [
    ("p1", "person", "Rahul Sharma", ["Rahul S."], {"occupation": "Freight Coordinator", "phone": "9876543210"}),
    ("p2", "person", "Amit Verma", ["A.V."], {"occupation": "Logistics Manager", "phone": "8822345678"}),
    ("p3", "person", "Vikram Singh", ["Vicky"], {"occupation": "Trading Consultant", "phone": "9911223344"}),
    ("p4", "person", "Neha Sharma", [], {"occupation": "Accountant", "phone": "9123456780"}),
    ("p5", "person", "Sanjay Mehta", [], {"occupation": "Freight Operator"}),
    ("p6", "person", "Priya Nair", [], {"occupation": "Finance Associate"}),
    ("p7", "person", "Karan Malhotra", [], {"occupation": "Unknown"}),
    ("p8", "person", "Suresh Yadav", [], {"occupation": "Trading Associate"}),
    ("p9", "person", "Anjali Kapoor", [], {"occupation": "Clerk"}),
    ("p10", "person", "Deepak Chawla", [], {"occupation": "Unknown"}),
    ("ph1", "phone", "9876543210", [], {"carrier": "Demo Telecom", "registered": True}),
    ("ph2", "phone", "8822345678", [], {"carrier": "Demo Telecom", "registered": True}),
    ("ph3", "phone", "9911223344", [], {"carrier": "Demo Telecom", "registered": True}),
    ("ph4", "phone", "9090909090", [], {"carrier": "Demo Telecom", "registered": True}),
    ("ph5", "phone", "9123456780", [], {"carrier": "Demo Telecom", "registered": True}),
    ("l1", "location", "Noida Sector 62", [], {}),
    ("l2", "location", "Delhi", [], {}),
    ("l3", "location", "Connaught Place, Delhi", [], {}),
    ("l4", "location", "Gurugram", [], {}),
    ("l5", "location", "Ghaziabad", [], {}),
    ("o1", "organization", "Shivam Logistics Pvt. Ltd.", ["Shivam Logistics"], {"sector": "Logistics"}),
    ("o2", "organization", "Alpha Trading Co.", ["Alpha Trading"], {"sector": "Trading"}),
    ("o3", "organization", "Metro Freight Co.", ["Metro Freight"], {"sector": "Logistics"}),
    ("o4", "organization", "Nova Finserv", [], {"sector": "Finance"}),
    ("v1", "vehicle", "DL 8C AA 1234", [], {"model": "Sedan"}),
    ("v2", "vehicle", "HR 26 XX 5678", [], {"model": "Van"}),
    ("t1", "transaction", "Rs 2,45,000", [], {"txn_type": "NEFT", "amount": 245000, "date": "2026-01-14"}),
    ("t2", "transaction", "Rs 1,50,000", [], {"txn_type": "RTGS", "amount": 150000, "date": "2026-01-19"}),
    ("t3", "transaction", "Rs 80,000", [], {"txn_type": "UPI", "amount": 80000, "date": "2026-01-21"}),
]

# (source, target, type, source_ref, date, confidence, attributes)
CORE_RELATIONSHIPS = [
    ("p1", "p2", "MET", "FIR2026-0147", "2026-01-10", 0.95, {}),
    ("p1", "p2", "CALLED", "CDR-9876543210", "2026-01-11", 0.92, {"call_count": 12}),
    ("p1", "ph1", "OWNED", "Telecom KYC", "2026-01-02", 1.0, {}),
    ("p1", "ph2", "OWNED", "Telecom KYC", "2026-01-02", 0.85, {}),
    ("p2", "ph3", "OWNED", "Telecom KYC", "2026-01-02", 1.0, {}),
    ("p3", "ph4", "OWNED", "Telecom KYC", "2026-01-02", 1.0, {}),
    ("p4", "ph5", "OWNED", "Telecom KYC", "2026-01-02", 1.0, {}),
    ("p1", "l1", "VISITED", "Surveillance Report SR-118", "2026-01-10", 0.88, {"visit_count": 6}),
    ("p1", "l3", "VISITED", "Surveillance Report SR-119", "2026-01-12", 0.80, {"visit_count": 8}),
    ("p2", "l2", "VISITED", "Surveillance Report SR-120", "2026-01-12", 0.75, {"visit_count": 3}),
    ("p2", "l3", "VISITED", "Surveillance Report SR-121", "2026-01-12", 0.70, {"visit_count": 2}),
    ("p3", "l2", "VISITED", "Surveillance Report SR-122", "2026-01-13", 0.70, {"visit_count": 2}),
    ("p1", "v1", "OWNED", "Vehicle Registration RC-4471", "2026-01-02", 0.90, {}),
    ("p3", "v2", "OWNED", "Vehicle Registration RC-5582", "2026-01-02", 0.90, {}),
    ("p2", "o1", "WORKED_FOR", "Employment Record ER-771", "2026-01-02", 0.93, {}),
    ("p3", "o2", "ASSOCIATED_WITH", "FIR2026-0147", "2026-01-13", 0.70, {}),
    ("p5", "o3", "WORKED_FOR", "Employment Record ER-802", "2026-01-02", 0.90, {}),
    ("p6", "o4", "WORKED_FOR", "Employment Record ER-855", "2026-01-02", 0.88, {}),
    ("p8", "o2", "WORKED_FOR", "Employment Record ER-861", "2026-01-02", 0.85, {}),
    ("p9", "o3", "ASSOCIATED_WITH", "Employment Record ER-870", "2026-01-02", 0.60, {}),
    ("p5", "o1", "ASSOCIATED_WITH", "Surveillance Report SR-130", "2026-01-15", 0.55, {}),
    ("p4", "o1", "ASSOCIATED_WITH", "Surveillance Report SR-131", "2026-01-15", 0.50, {}),
    ("p2", "t1", "TRANSFERRED_MONEY", "Bank Statement BS-2201", "2026-01-14", 0.97, {"amount": 245000}),
    ("t1", "o1", "ASSOCIATED_WITH", "Bank Statement BS-2201", "2026-01-14", 0.97, {}),
    ("p1", "t2", "TRANSFERRED_MONEY", "Bank Statement BS-2244", "2026-01-19", 0.90, {"amount": 150000}),
    ("t2", "o2", "ASSOCIATED_WITH", "Bank Statement BS-2244", "2026-01-19", 0.90, {}),
    ("p3", "t3", "TRANSFERRED_MONEY", "Bank Statement BS-2299", "2026-01-21", 0.82, {"amount": 80000}),
    ("t3", "o4", "ASSOCIATED_WITH", "Bank Statement BS-2299", "2026-01-21", 0.82, {}),
    ("p2", "p3", "CALLED", "CDR-9911223344", "2026-01-18", 0.80, {"call_count": 5}),
    ("p4", "p2", "CALLED", "CDR-9123456780", "2026-01-16", 0.60, {"call_count": 2}),
    ("p1", "p4", "ASSOCIATED_WITH", "Surveillance Report SR-140", "2026-01-16", 0.60, {}),
    ("p5", "p3", "MET", "Surveillance Report SR-141", "2026-01-22", 0.65, {}),
    ("p6", "p3", "CALLED", "CDR-VIKRAM-02", "2026-01-20", 0.55, {"call_count": 3}),
    ("p7", "p2", "ASSOCIATED_WITH", "Surveillance Report SR-142", "2026-01-17", 0.50, {}),
    ("p8", "p3", "MET", "Surveillance Report SR-143", "2026-01-23", 0.55, {}),
    ("p9", "p5", "CALLED", "CDR-ANJALI-01", "2026-01-24", 0.40, {"call_count": 1}),
    ("p10", "p8", "CALLED", "CDR-DEEPAK-01", "2026-01-05", 0.35, {"call_count": 1}),
    ("p10", "l5", "VISITED", "Surveillance Report SR-150", "2026-01-05", 0.30, {"visit_count": 1}),
    ("p7", "l2", "VISITED", "Surveillance Report SR-151", "2026-01-17", 0.45, {"visit_count": 1}),
    ("p9", "l4", "VISITED", "Surveillance Report SR-152", "2026-01-18", 0.40, {"visit_count": 1}),
    ("p6", "l5", "VISITED", "Surveillance Report SR-153", "2026-01-19", 0.40, {"visit_count": 1}),
]

# Sample unstructured text used by the AI & NLP Analysis page. Verbatim from
# the project material (REQUIREMENTS.md section 5).
SAMPLE_FIR_TEXT = (
    "Rahul Sharma met Amit Verma at Noida Sector 62 on 10 January. "
    "Rahul contacted Amit several times using phone number 9876543210. "
    "Amit later transferred Rs 2,45,000 to Shivam Logistics."
)

SAMPLE_WS_TEXT = (
    "On Day 9 the complainant reported being followed on her commute between "
    "her residence and her workplace. A two-wheeler bearing registration "
    "DL-0X-XX-4471 was sighted at the residence on two occasions. "
    "The unregistered number +91-70xxxx4482 sent messages to the complainant "
    "over the preceding fortnight. On Day 14 a confrontation occurred at the "
    "confrontation site and was witnessed by a neighbour."
)


# ===========================================================================
# WOMEN SAFETY CONTEXT STATISTICS
# ---------------------------------------------------------------------------
# REAL, publicly reported statistics, retained for problem context only.
# Classification REFERENCE, never mixed into case analytics.
# Sources: NCRB / Delhi Police figures as reported by Deccan Herald and
# The Tribune, transcribed from legacy-prototype/js/data-womensafety.js.
# ===========================================================================

DELHI_CONTEXT_STATS = {
    "classification": "REFERENCE",
    "disclaimer": (
        "Publicly reported statistics included for problem context only. "
        "These figures are unrelated to the synthetic case data in this "
        "platform and are never used in any analytical computation."
    ),
    "headline": [
        {
            "value": "13,366",
            "label": "Total crimes against women reported in Delhi in 2023 - the highest among Indian metro cities",
            "source": "NCRB, via Deccan Herald",
        },
        {
            "value": "~4,000",
            "label": "Kidnapping & abduction of women/girls reported in Delhi in 2023",
            "source": "NCRB, via Deccan Herald",
        },
        {
            "value": "#1 Metro",
            "label": "Delhi ranked highest among metros for rape, dowry-death and cruelty-by-husband cases in 2023",
            "source": "NCRB, via Deccan Herald",
        },
    ],
    "year_over_year": {
        "title": "Reported crimes against women in Delhi - 2023 vs 2024",
        "source": "Deccan Herald, citing Delhi Police data",
        "categories": [
            {"label": "Rape", "y2023": 2141, "y2024": 2076},
            {"label": "Molestation", "y2023": 2345, "y2024": 2037},
            {"label": "Eve-teasing", "y2023": 381, "y2024": 362},
        ],
    },
    "quarterly": {
        "title": "Q1 2024 vs Q1 2025",
        "source": "The Tribune, citing Delhi Police data",
        "rows": [
            {"label": "Rape", "q1_2024": 455, "q1_2025": 370, "change": "-18.7%"},
            {"label": "Molestation", "q1_2024": 444, "q1_2025": 379, "change": "-14.6%"},
            {"label": "Eve-teasing", "q1_2024": 74, "q1_2025": 63, "change": "-14.9%"},
        ],
    },
    "note": (
        "Police commentary attributes the decline partly to enhanced night "
        "patrolling, mobile women-police teams and campus security - but "
        "sustained reduction requires better repeat-offender identification "
        "and cross-case linkage, the gap this module targets."
    ),
}


# Relationship type -> display label. Combined vocabulary from both cases.
RELATIONSHIP_LABELS = {
    "CALLED": "Called",
    "MET": "Met",
    "VISITED": "Visited",
    "OWNED": "Owned",
    "ASSOCIATED_WITH": "Associated With",
    "TRANSFERRED_MONEY": "Transferred Money",
    "WORKED_FOR": "Worked For",
    "TRAVELLED_TO": "Travelled To",
    "CONNECTED_TO": "Connected To",
    "complaint_filed_against": "Complaint Filed Against",
    "registered_owner_of": "Registered Owner Of",
    "believed_to_use": "Believed To Use",
    "purchased_via": "Purchased Via",
    "id_proof_matches": "ID Proof Matches",
    "alias_of": "Alias Of",
    "named_accused_in": "Named Accused In",
    "sighted_at": "Sighted At",
    "resides_at": "Resides At",
    "commutes_to": "Commutes To",
    "location_of": "Location Of",
    "witnessed": "Witnessed",
    "sent_messages_to": "Sent Messages To",
    "linked_by_metadata_to": "Linked By Metadata",
    "followed": "Followed",
}

ENTITY_TYPE_META = {
    "person": {"label": "Person", "color": "#6d4fd1", "glyph": "P"},
    "phone": {"label": "Phone", "color": "#1f9d63", "glyph": "☎"},
    "location": {"label": "Location", "color": "#2f6fed", "glyph": "◉"},
    "organization": {"label": "Organization", "color": "#e07a1f", "glyph": "O"},
    "vehicle": {"label": "Vehicle", "color": "#6b7280", "glyph": "V"},
    "transaction": {"label": "Transaction", "color": "#c9a227", "glyph": "₹"},
    "social": {"label": "Social Handle", "color": "#0ea5a5", "glyph": "@"},
    "event": {"label": "Event", "color": "#c94f7c", "glyph": "E"},
    "case_record": {"label": "Prior Case", "color": "#4a5578", "glyph": "C"},
}
