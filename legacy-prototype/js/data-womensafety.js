/*
 * TriNetra — Women Safety Module dataset.
 * Source: TriNetra_WomenSafety_DemoDataPack.pdf, Sections A-E.
 *
 * Section A (DELHI_CONTEXT_STATS below) is REAL, publicly reported, cited
 * statistics (NCRB / Delhi Police, via Deccan Herald & The Tribune), included
 * for problem-context only.
 *
 * Everything from Section B onward (WS_ENTITIES, WS_RELATIONSHIPS,
 * WOMEN_SAFETY_CASE, WS_NARRATIVE_EVENTS) is ENTIRELY FICTIONAL synthetic
 * demonstration data for case DEMO/WS-2026-0417. No real victim, suspect,
 * witness, phone number, vehicle, or police station is represented.
 */

const WS_ENTITIES = [
  { id: "V1", type: "person", name: "A. Sharma", aliases: [], meta: { role: "Victim" } },
  { id: "S1", type: "person", name: "R. Verma", aliases: [], meta: { role: "Primary Suspect" } },
  { id: "S2", type: "person", name: "S. Mehta", aliases: [], meta: { role: "Linked Identity — 2024 FIR (other district)" } },
  { id: "W1", type: "person", name: "Neighbour (W1)", aliases: [], meta: { role: "Witness" } },
  { id: "PH1", type: "phone", name: "+91-98xxxx1123", aliases: [], meta: { registered: true, note: "Registered to S1" } },
  { id: "PH2", type: "phone", name: "+91-70xxxx4482", aliases: [], meta: { registered: false, note: "Unregistered — believed used by S1" } },
  { id: "SOC1", type: "social", name: "@user_4471", aliases: [], meta: { platform: "Social media handle (authorized request)" } },
  { id: "VEH1", type: "vehicle", name: "DL-0X-XX-4471", aliases: [], meta: { model: "Two-wheeler" } },
  { id: "TXN1", type: "transaction", name: "SIM Purchase Record", aliases: [], meta: { txnType: "Telecom retailer KYC" } },
  { id: "LOC1", type: "location", name: "Victim Residence (NW Delhi)", aliases: [], meta: {} },
  { id: "LOC2", type: "location", name: "Victim Workplace", aliases: [], meta: {} },
  { id: "LOC3", type: "location", name: "Confrontation Site", aliases: [], meta: {} },
  { id: "EVT2", type: "event", name: "Escalation Incident (Day 14)", aliases: [], meta: {} },
  { id: "CASE_PRIOR", type: "case_record", name: "2024 Stalking FIR (Other District)", aliases: [], meta: {} },
];

let _wsEdgeId = 0;
function wsEdge(source, target, type, opts) {
  _wsEdgeId += 1;
  return Object.assign(
    {
      id: "we" + _wsEdgeId,
      source,
      target,
      type,
      evidenceSource: "Case FIR text (DEMO/WS-2026-0417)",
      timestamp: "",
      confidence: 1,
      verification: "unreviewed",
      isObserved: true,
      candidateHiddenLink: false,
    },
    opts || {}
  );
}

const WS_RELATIONSHIPS = [];
function addWsEdge(source, target, type, opts) {
  WS_RELATIONSHIPS.push(wsEdge(source, target, type, opts));
}
function wsFindEdgeId(source, target, type) {
  const hit = WS_RELATIONSHIPS.find(
    (r) =>
      r.type === type &&
      ((r.source === source && r.target === target) || (r.source === target && r.target === source))
  );
  return hit ? hit.id : null;
}

(function buildWsRelationships() {
  // -- Observed relationships (PDF Section C.3) --
  addWsEdge("V1", "S1", "complaint_filed_against", { confidence: 1.0, evidenceSource: "Case FIR — Day 1 complaint" });
  addWsEdge("S1", "PH1", "registered_owner_of", { confidence: 1.0, evidenceSource: "Telecom subscriber record" });
  addWsEdge("PH2", "TXN1", "purchased_via", { confidence: 1.0, evidenceSource: "Telecom retailer KYC record" });
  addWsEdge("TXN1", "S1", "id_proof_matches", { confidence: 0.95, evidenceSource: "Telecom retailer KYC record" });
  addWsEdge("S2", "CASE_PRIOR", "named_accused_in", { confidence: 1.0, evidenceSource: "Cross-district FIR database" });
  addWsEdge("S1", "VEH1", "registered_owner_of", { confidence: 1.0, evidenceSource: "RTO / RC records" });
  addWsEdge("VEH1", "LOC1", "sighted_at", { confidence: 0.9, evidenceSource: "Surveillance — Day 9" });
  addWsEdge("VEH1", "LOC3", "sighted_at", { confidence: 0.92, evidenceSource: "Witness statement — Day 14" });
  addWsEdge("V1", "LOC1", "resides_at", { confidence: 1.0, evidenceSource: "Case FIR text" });
  addWsEdge("V1", "LOC2", "commutes_to", { confidence: 1.0, evidenceSource: "Case FIR text" });
  addWsEdge("LOC3", "EVT2", "location_of", { confidence: 1.0, evidenceSource: "Witness statement" });
  addWsEdge("W1", "EVT2", "witnessed", { confidence: 1.0, evidenceSource: "Witness statement — Day 14" });
  addWsEdge("SOC1", "V1", "sent_messages_to", { confidence: 1.0, evidenceSource: "Platform metadata (authorized request)" });

  // -- Inferred / candidate hidden links (PDF Section C.3, "Inferred" rows) --
  // These plug into the existing evidence-modal + accept/reject review UI.
  addWsEdge("S1", "PH2", "believed_to_use", {
    confidence: 0.78,
    isObserved: false,
    candidateHiddenLink: true,
    evidenceSource: "Derived (call-pattern correlation)",
    evidenceRefs: [wsFindEdgeId("PH2", "TXN1", "purchased_via"), wsFindEdgeId("TXN1", "S1", "id_proof_matches")].filter(Boolean),
    explanation:
      "TriNetra flagged PH2 (+91-70xxxx4482), an unregistered number, as likely used by R. Verma (S1) based on call-pattern correlation with his registered number and a SIM-purchase record (TXN1) whose ID proof matches S1. This is a candidate lead, not a registered ownership record — presented for investigator confirmation.",
  });
  addWsEdge("S1", "S2", "alias_of", {
    confidence: 0.87,
    isObserved: false,
    candidateHiddenLink: true,
    evidenceSource: "Derived (entity resolution)",
    evidenceRefs: [wsFindEdgeId("S2", "CASE_PRIOR", "named_accused_in")].filter(Boolean),
    explanation:
      "Entity resolution matched R. Verma (S1) to a prior identity, S. Mehta (S2), named in a stalking FIR filed in a different district in 2024 — a link the two siloed case records did not previously share. If confirmed, this surfaces S1 in the Women Safety Module's repeat-offender view.",
  });
  addWsEdge("SOC1", "PH2", "linked_by_metadata_to", {
    confidence: 0.71,
    isObserved: false,
    candidateHiddenLink: true,
    evidenceSource: "Derived (platform metadata correlation)",
    evidenceRefs: [wsFindEdgeId("SOC1", "V1", "sent_messages_to"), wsFindEdgeId("S1", "PH2", "believed_to_use")].filter(Boolean),
    explanation:
      "Platform metadata for the social handle @user_4471 (SOC1) correlates with the unregistered number PH2 via account-registration and device-fingerprint overlap. Lower-confidence candidate link, pending further corroboration.",
  });
})();

function wsGetEntity(id) {
  return WS_ENTITIES.find((e) => e.id === id);
}
function wsEdgesForEntity(id) {
  return WS_RELATIONSHIPS.filter((r) => r.source === id || r.target === id);
}
function wsNeighborsOf(id) {
  const ids = new Set();
  wsEdgesForEntity(id).forEach((r) => ids.add(r.source === id ? r.target : r.source));
  return Array.from(ids).map(wsGetEntity).filter(Boolean);
}

// Case metadata + the exact AI analytics readout from PDF Section C.5.
const WOMEN_SAFETY_CASE = {
  id: "DEMO/WS-2026-0417",
  title: "Stalking & Harassment Investigation",
  status: "ACTIVE",
  victimId: "V1",
  suspectId: "S1",
  riskScore: {
    entityId: "S1",
    label: "HIGH",
    confidence: 0.91,
    reason: "Repeat-offender pattern match, escalation trend across 14 days, alias link to a prior stalking FIR.",
  },
  hiddenLink: {
    fromId: "S1",
    toId: "S2",
    confidence: 0.87,
    reason: "Entity resolution connected two identities previously siloed across separate district FIR systems.",
  },
  suspiciousCluster: {
    entityIds: ["PH2", "TXN1", "VEH1"],
    reason: "An unregistered number, a SIM purchase, and a vehicle converge on the same individual across two locations.",
  },
  recommendedAction: {
    action: "Escalate + Protective Measures",
    note: "Investigator-in-the-loop confirmation requested before any protective or enforcement action.",
  },
};

// Case narrative (PDF Section C.1), for the shared timeline component.
const WS_NARRATIVE_EVENTS = [
  {
    day: "Day 1",
    title: "Complaint filed",
    tag: "complaint",
    description:
      'Victim V1 (alias "A. Sharma") files a complaint at the local police station reporting repeated unwanted calls and messages from an unknown number over the preceding two weeks.',
  },
  {
    day: "Day 9",
    title: "Followed on commute",
    tag: "surveillance",
    description:
      "V1 reports being followed on her commute between her residence (LOC1) and workplace (LOC2). A two-wheeler (VEH1, DL-0X-XX-4471) is sighted near LOC1 on two occasions.",
  },
  {
    day: "Day 14",
    title: "In-person confrontation",
    tag: "escalation",
    description:
      "A confrontation occurs near LOC3, witnessed by a neighbour (W1). VEH1 is sighted at the scene. The case is escalated and flagged for AI-assisted analysis.",
  },
  {
    day: "Day 15",
    title: "AI/NLP ingestion & extraction",
    tag: "analysis",
    description:
      'TriNetra ingests the case file, call records, and a SIM-purchase record. NLP identifies primary suspect S1 ("R. Verma") as registered owner of VEH1 and phone PH1, and flags a second, unregistered number PH2 as "believed to use."',
  },
  {
    day: "Day 16",
    title: "Hidden link confirmed, risk assigned",
    tag: "resolution",
    description:
      'Entity resolution flags a 0.87-confidence alias match between S1 and a prior identity S2 ("S. Mehta") from a 2024 stalking FIR in another district. The investigator reviews and validates the link; TriNetra assigns S1 a HIGH risk score.',
  },
];

// Section A — REAL, cited statistics (context only, unrelated to the
// synthetic case above). Sources: Deccan Herald & The Tribune, citing
// NCRB / Delhi Police data.
const DELHI_CONTEXT_STATS = {
  headline: [
    {
      value: "13,366",
      label: "Total crimes against women reported in Delhi in 2023 — the highest among Indian metro cities",
      source: "NCRB, via Deccan Herald",
    },
    {
      value: "~4,000",
      label: "Kidnapping & abduction of women/girls reported in Delhi in 2023",
      source: "NCRB, via Deccan Herald",
    },
    {
      value: "#1 Metro",
      label: "Delhi ranked highest among metros for rape, dowry-death, and cruelty-by-husband cases in 2023",
      source: "NCRB, via Deccan Herald",
    },
  ],
  yearOverYear: {
    title: "Reported crimes against women in Delhi — 2023 vs 2024",
    source: "Deccan Herald, citing Delhi Police data",
    categories: [
      { label: "Rape", y2023: 2141, y2024: 2076 },
      { label: "Molestation", y2023: 2345, y2024: 2037 },
      { label: "Eve-teasing", y2023: 381, y2024: 362 },
    ],
  },
  quarterly: {
    title: "Q1 2024 vs Q1 2025",
    source: "The Tribune, citing Delhi Police data",
    rows: [
      { label: "Rape", q1_2024: 455, q1_2025: 370, change: "-18.7%" },
      { label: "Molestation", q1_2024: 444, q1_2025: 379, change: "-14.6%" },
      { label: "Eve-teasing", q1_2024: 74, q1_2025: 63, change: "-14.9%" },
    ],
  },
  note: "Police commentary attributes the decline partly to enhanced night patrolling, mobile women-police teams, and campus security — but sustained reduction requires better repeat-offender identification and cross-case linkage, the gap this module targets.",
};
