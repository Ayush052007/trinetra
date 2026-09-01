/*
 * TriNetra synthetic demo dataset.
 * All names, numbers, organizations and events below are FICTIONAL and generated
 * for demonstration purposes only. No real persons, phone numbers or case data
 * are represented.
 */

const ENTITY_TYPES = {
  person: { label: "Person", color: "#6d4fd1", icon: "person" },
  phone: { label: "Phone", color: "#1f9d63", icon: "phone" },
  location: { label: "Location", color: "#2f6fed", icon: "location" },
  organization: { label: "Organization", color: "#e07a1f", icon: "org" },
  vehicle: { label: "Vehicle", color: "#6b7280", icon: "vehicle" },
  transaction: { label: "Transaction", color: "#c9a227", icon: "transaction" },
  social: { label: "Social Handle", color: "#0ea5a5", icon: "social" },
  event: { label: "Event", color: "#c94f7c", icon: "event" },
  case_record: { label: "Prior Case", color: "#4a5578", icon: "case" },
};

const ENTITIES = [
  // People
  { id: "p1", type: "person", name: "Rahul Sharma", aliases: ["Rahul S."], meta: { occupation: "Freight Coordinator" } },
  { id: "p2", type: "person", name: "Amit Verma", aliases: ["A.V."], meta: { occupation: "Logistics Manager" } },
  { id: "p3", type: "person", name: "Vikram Singh", aliases: ["Vicky"], meta: { occupation: "Trading Consultant" } },
  { id: "p4", type: "person", name: "Neha Sharma", aliases: [], meta: { occupation: "Accountant" } },
  { id: "p5", type: "person", name: "Sanjay Mehta", aliases: [], meta: { occupation: "Freight Operator" } },
  { id: "p6", type: "person", name: "Priya Nair", aliases: [], meta: { occupation: "Finance Associate" } },
  { id: "p7", type: "person", name: "Karan Malhotra", aliases: [], meta: { occupation: "Unknown" } },
  { id: "p8", type: "person", name: "Suresh Yadav", aliases: [], meta: { occupation: "Trading Associate" } },
  { id: "p9", type: "person", name: "Anjali Kapoor", aliases: [], meta: { occupation: "Clerk" } },
  { id: "p10", type: "person", name: "Deepak Chawla", aliases: [], meta: { occupation: "Unknown" } },

  // Phones
  { id: "ph1", type: "phone", name: "9876543210", aliases: [], meta: { carrier: "Demo Telecom" } },
  { id: "ph2", type: "phone", name: "8822345678", aliases: [], meta: { carrier: "Demo Telecom" } },
  { id: "ph3", type: "phone", name: "9911223344", aliases: [], meta: { carrier: "Demo Telecom" } },
  { id: "ph4", type: "phone", name: "9090909090", aliases: [], meta: { carrier: "Demo Telecom" } },
  { id: "ph5", type: "phone", name: "9123456780", aliases: [], meta: { carrier: "Demo Telecom" } },

  // Locations
  { id: "l1", type: "location", name: "Noida Sector 62", aliases: [], meta: {} },
  { id: "l2", type: "location", name: "Delhi", aliases: [], meta: {} },
  { id: "l3", type: "location", name: "Connaught Place, Delhi", aliases: [], meta: {} },
  { id: "l4", type: "location", name: "Gurugram", aliases: [], meta: {} },
  { id: "l5", type: "location", name: "Ghaziabad", aliases: [], meta: {} },

  // Organizations
  { id: "o1", type: "organization", name: "Shivam Logistics Pvt. Ltd.", aliases: [], meta: { sector: "Logistics" } },
  { id: "o2", type: "organization", name: "Alpha Trading Co.", aliases: [], meta: { sector: "Trading" } },
  { id: "o3", type: "organization", name: "Metro Freight Co.", aliases: [], meta: { sector: "Logistics" } },
  { id: "o4", type: "organization", name: "Nova Finserv", aliases: [], meta: { sector: "Finance" } },

  // Vehicles
  { id: "v1", type: "vehicle", name: "DL 8C AA 1234", aliases: [], meta: { model: "Sedan" } },
  { id: "v2", type: "vehicle", name: "HR 26 XX 5678", aliases: [], meta: { model: "Van" } },

  // Transactions
  { id: "t1", type: "transaction", name: "₹2,45,000", aliases: [], meta: { txnType: "NEFT", date: "2026-01-14" } },
  { id: "t2", type: "transaction", name: "₹1,50,000", aliases: [], meta: { txnType: "RTGS", date: "2026-01-19" } },
  { id: "t3", type: "transaction", name: "₹80,000", aliases: [], meta: { txnType: "UPI", date: "2026-01-21" } },
];

// Relationship types shown in the legend / evidence panel.
const REL_LABELS = {
  CALLED: "Called",
  MET: "Met",
  VISITED: "Visited",
  OWNED: "Owned",
  ASSOCIATED_WITH: "Associated With",
  TRANSFERRED_MONEY: "Transferred Money",
  WORKED_FOR: "Worked For",
  TRAVELLED_TO: "Travelled To",
  CONNECTED_TO: "Connected To (Inferred)",
  // Women Safety Module relationship types (case DEMO/WS-2026-0417)
  complaint_filed_against: "Complaint Filed Against",
  registered_owner_of: "Registered Owner Of",
  believed_to_use: "Believed To Use (Inferred)",
  purchased_via: "Purchased Via",
  id_proof_matches: "ID Proof Matches",
  alias_of: "Alias Of (Inferred)",
  named_accused_in: "Named Accused In",
  sighted_at: "Sighted At",
  resides_at: "Resides At",
  commutes_to: "Commutes To",
  location_of: "Location Of",
  witnessed: "Witnessed",
  sent_messages_to: "Sent Messages To",
  linked_by_metadata_to: "Linked By Metadata (Inferred)",
};

// Shared entity badge glyph, used by both the main app views and the Women
// Safety module.
function entityIconLabel(type) {
  return (
    {
      person: "P",
      phone: "☎",
      location: "📍",
      organization: "O",
      vehicle: "🚗",
      transaction: "₹",
      social: "@",
      event: "⚑",
      case_record: "⚖",
    }[type] || "?"
  );
}

let _edgeId = 0;
function edge(source, target, type, opts) {
  _edgeId += 1;
  return Object.assign(
    {
      id: "e" + _edgeId,
      source,
      target,
      type,
      evidenceSource: "FIR2026-0147",
      timestamp: "2026-01-10",
      confidence: 0.9,
      verification: "unreviewed",
      isObserved: true,
      candidateHiddenLink: false,
    },
    opts || {}
  );
}

const RELATIONSHIPS = [];
function addEdge(source, target, type, opts) {
  RELATIONSHIPS.push(edge(source, target, type, opts));
}
function findEdgeId(source, target, type) {
  const hit = RELATIONSHIPS.find(
    (r) =>
      r.type === type &&
      ((r.source === source && r.target === target) || (r.source === target && r.target === source))
  );
  return hit ? hit.id : null;
}

(function buildRelationships() {
  // Core case chain: Rahul -> Amit -> Vikram -> orgs -> transactions
  addEdge("p1", "p2", "MET", { timestamp: "2026-01-10", evidenceSource: "FIR2026-0147", confidence: 0.95, callCount: 1 });
  addEdge("p1", "p2", "CALLED", { timestamp: "2026-01-11", evidenceSource: "CDR-9876543210", confidence: 0.92, callCount: 12 });
  addEdge("p1", "ph1", "OWNED", { confidence: 1, evidenceSource: "Telecom KYC" });
  addEdge("p1", "ph2", "OWNED", { confidence: 0.85, evidenceSource: "Telecom KYC" });
  addEdge("p2", "ph3", "OWNED", { confidence: 1, evidenceSource: "Telecom KYC" });
  addEdge("p3", "ph4", "OWNED", { confidence: 1, evidenceSource: "Telecom KYC" });
  addEdge("p4", "ph5", "OWNED", { confidence: 1, evidenceSource: "Telecom KYC" });

  addEdge("p1", "l1", "VISITED", { evidenceSource: "Surveillance Report SR-118", confidence: 0.88, visitCount: 6 });
  addEdge("p1", "l3", "VISITED", { evidenceSource: "Surveillance Report SR-119", confidence: 0.8, visitCount: 8 });
  addEdge("p2", "l2", "VISITED", { evidenceSource: "Surveillance Report SR-120", confidence: 0.75, visitCount: 3 });
  addEdge("p2", "l3", "VISITED", { evidenceSource: "Surveillance Report SR-121", confidence: 0.7, visitCount: 2 });
  addEdge("p3", "l2", "VISITED", { evidenceSource: "Surveillance Report SR-122", confidence: 0.7, visitCount: 2 });

  addEdge("p1", "v1", "OWNED", { evidenceSource: "Vehicle Registration RC-4471", confidence: 0.9 });
  addEdge("p3", "v2", "OWNED", { evidenceSource: "Vehicle Registration RC-5582", confidence: 0.9 });

  addEdge("p2", "o1", "WORKED_FOR", { evidenceSource: "Employment Record ER-771", confidence: 0.93 });
  addEdge("p3", "o2", "ASSOCIATED_WITH", { evidenceSource: "FIR2026-0147", confidence: 0.7 });
  addEdge("p5", "o3", "WORKED_FOR", { evidenceSource: "Employment Record ER-802", confidence: 0.9 });
  addEdge("p6", "o4", "WORKED_FOR", { evidenceSource: "Employment Record ER-855", confidence: 0.88 });
  addEdge("p8", "o2", "WORKED_FOR", { evidenceSource: "Employment Record ER-861", confidence: 0.85 });
  addEdge("p9", "o3", "ASSOCIATED_WITH", { evidenceSource: "Employment Record ER-870", confidence: 0.6 });
  addEdge("p5", "o1", "ASSOCIATED_WITH", { evidenceSource: "Surveillance Report SR-130", confidence: 0.55 });
  addEdge("p4", "o1", "ASSOCIATED_WITH", { evidenceSource: "Surveillance Report SR-131", confidence: 0.5 });

  addEdge("p2", "t1", "TRANSFERRED_MONEY", { evidenceSource: "Bank Statement BS-2201", confidence: 0.97, timestamp: "2026-01-14" });
  addEdge("t1", "o1", "ASSOCIATED_WITH", { evidenceSource: "Bank Statement BS-2201", confidence: 0.97, timestamp: "2026-01-14" });
  addEdge("p1", "t2", "TRANSFERRED_MONEY", { evidenceSource: "Bank Statement BS-2244", confidence: 0.9, timestamp: "2026-01-19" });
  addEdge("t2", "o2", "ASSOCIATED_WITH", { evidenceSource: "Bank Statement BS-2244", confidence: 0.9, timestamp: "2026-01-19" });
  addEdge("p3", "t3", "TRANSFERRED_MONEY", { evidenceSource: "Bank Statement BS-2299", confidence: 0.82, timestamp: "2026-01-21" });
  addEdge("t3", "o4", "ASSOCIATED_WITH", { evidenceSource: "Bank Statement BS-2299", confidence: 0.82, timestamp: "2026-01-21" });

  addEdge("p2", "p3", "CALLED", { evidenceSource: "CDR-9911223344", confidence: 0.8, timestamp: "2026-01-18", callCount: 5 });
  addEdge("p4", "p2", "CALLED", { evidenceSource: "CDR-9123456780", confidence: 0.6, timestamp: "2026-01-16", callCount: 2 });
  addEdge("p1", "p4", "ASSOCIATED_WITH", { evidenceSource: "Surveillance Report SR-140", confidence: 0.6 });
  addEdge("p5", "p3", "MET", { evidenceSource: "Surveillance Report SR-141", confidence: 0.65, timestamp: "2026-01-22" });
  addEdge("p6", "p3", "CALLED", { evidenceSource: "CDR-VIKRAM-02", confidence: 0.55, timestamp: "2026-01-20", callCount: 3 });
  addEdge("p7", "p2", "ASSOCIATED_WITH", { evidenceSource: "Surveillance Report SR-142", confidence: 0.5 });
  addEdge("p8", "p3", "MET", { evidenceSource: "Surveillance Report SR-143", confidence: 0.55, timestamp: "2026-01-23" });
  addEdge("p9", "p5", "CALLED", { evidenceSource: "CDR-ANJALI-01", confidence: 0.4, timestamp: "2026-01-24", callCount: 1 });

  // Isolated / one-off relationship (contrast vs the persistent Rahul<->Amit link)
  addEdge("p10", "p8", "CALLED", { evidenceSource: "CDR-DEEPAK-01", confidence: 0.35, timestamp: "2026-01-05", callCount: 1 });
  addEdge("p10", "l5", "VISITED", { evidenceSource: "Surveillance Report SR-150", confidence: 0.3, visitCount: 1 });
  addEdge("p7", "l2", "VISITED", { evidenceSource: "Surveillance Report SR-151", confidence: 0.45, visitCount: 1 });
  addEdge("p9", "l4", "VISITED", { evidenceSource: "Surveillance Report SR-152", confidence: 0.4, visitCount: 1 });
  addEdge("p6", "l5", "VISITED", { evidenceSource: "Surveillance Report SR-153", confidence: 0.4, visitCount: 1 });

  // Candidate hidden links (AI-surfaced, not directly observed anywhere).
  // Evidence is looked up by (source, target, type) rather than hardcoded
  // edge ids, so this stays correct if edges above are reordered/added to.
  addEdge("p1", "p3", "CONNECTED_TO", {
    evidenceSource: "Derived (graph inference)",
    confidence: 0.68,
    isObserved: false,
    candidateHiddenLink: true,
    evidenceRefs: [
      findEdgeId("p1", "p2", "CALLED"),
      findEdgeId("p2", "p3", "CALLED"),
      findEdgeId("p3", "o2", "ASSOCIATED_WITH"),
      findEdgeId("t1", "o1", "ASSOCIATED_WITH"),
      findEdgeId("t2", "o2", "ASSOCIATED_WITH"),
      findEdgeId("p2", "l2", "VISITED"),
      findEdgeId("p3", "l2", "VISITED"),
    ].filter(Boolean),
    explanation:
      "No direct call, meeting or transaction links Rahul Sharma and Vikram Singh. However, both share a common associate (Amit Verma), overlapping presence in Delhi, and a financial trail between organizations they are each connected to (Shivam Logistics ↔ Alpha Trading).",
  });
  addEdge("p4", "p3", "CONNECTED_TO", {
    evidenceSource: "Derived (graph inference)",
    confidence: 0.42,
    isObserved: false,
    candidateHiddenLink: true,
    evidenceRefs: [
      findEdgeId("p1", "p4", "ASSOCIATED_WITH"),
      findEdgeId("p1", "p2", "MET"),
      findEdgeId("p2", "p3", "CALLED"),
    ].filter(Boolean),
    explanation:
      "Neha Sharma has no observed direct contact with Vikram Singh, but is linked to him through two intermediate relationships (Rahul Sharma and Amit Verma).",
  });
})();

const CASES = [
  {
    id: "NX-2026-0147",
    title: "Financial Network Investigation",
    status: "ACTIVE",
    leadEntity: "p1",
  },
];

const SAMPLE_FIR_TEXT =
  "Rahul Sharma met Amit Verma at Noida Sector 62 on 10 January. Rahul contacted Amit several times using phone number 9876543210. Amit later transferred ₹2,45,000 to Shivam Logistics.";

const SAMPLE_EXTRACTION = {
  entities: [
    { type: "person", value: "Rahul Sharma", entityId: "p1" },
    { type: "person", value: "Amit Verma", entityId: "p2" },
    { type: "location", value: "Noida Sector 62", entityId: "l1" },
    { type: "phone", value: "9876543210", entityId: "ph1" },
    { type: "organization", value: "Shivam Logistics", entityId: "o1" },
    { type: "transaction", value: "₹2,45,000", entityId: "t1" },
  ],
  relationships: [
    { from: "Rahul Sharma", rel: "MET", to: "Amit Verma", edgeId: findEdgeId("p1", "p2", "MET") },
    { from: "Rahul Sharma", rel: "CONTACTED", to: "9876543210", edgeId: findEdgeId("p1", "ph1", "OWNED") },
    { from: "Amit Verma", rel: "TRANSFERRED_MONEY", to: "Shivam Logistics", edgeId: findEdgeId("p2", "t1", "TRANSFERRED_MONEY") },
  ],
};

// ---- Derived lookups / helpers -------------------------------------------

const ENTITY_BY_ID = {};
ENTITIES.forEach((e) => (ENTITY_BY_ID[e.id] = e));

function getEntity(id) {
  return ENTITY_BY_ID[id];
}

function edgesForEntity(id) {
  return RELATIONSHIPS.filter((r) => r.source === id || r.target === id);
}

function neighborsOf(id) {
  const ids = new Set();
  edgesForEntity(id).forEach((r) => {
    ids.add(r.source === id ? r.target : r.source);
  });
  return Array.from(ids).map(getEntity).filter(Boolean);
}

function searchEntities(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return [];
  return ENTITIES.filter((e) => {
    if (e.name.toLowerCase().includes(q)) return true;
    return e.aliases.some((a) => a.toLowerCase().includes(q));
  }).slice(0, 12);
}

// A simple, transparent (not black-box) degree-based priority rule.
// This is explicitly a structural signal, NOT a guilt/criminality score.
function investigationPriority(id) {
  const degree = edgesForEntity(id).length;
  if (degree >= 6) return { label: "HIGH", confidence: Math.min(0.95, 0.6 + degree * 0.03) };
  if (degree >= 3) return { label: "MEDIUM", confidence: 0.55 + degree * 0.03 };
  return { label: "LOW", confidence: 0.3 + degree * 0.03 };
}

// ---- Audit log -------------------------------------------------------------
// A real (in-memory, session-scoped) audit trail. Investigator actions such as
// accepting/rejecting an AI-suggested link or exporting a report push entries
// here live, so the Audit Logs page reflects what actually happened in the
// demo session rather than a static mock-up.

const AUDIT_LOG = [];

function logAudit(action, detail) {
  AUDIT_LOG.unshift({
    time: new Date(),
    actor: "Investigator (IO-114)",
    action,
    detail,
  });
  if (AUDIT_LOG.length > 300) AUDIT_LOG.length = 300;
}

(function seedAuditLog() {
  const now = Date.now();
  const seed = [
    [18, "Session started", "Secure investigator login"],
    [16, "Dashboard viewed", "Investigation Intelligence Dashboard"],
    [12, "Case opened", "NX-2026-0147 · Financial Network Investigation"],
    [7, "Case opened", "DEMO/WS-2026-0417 · Women Safety Module"],
  ];
  seed.forEach(([minsAgo, action, detail]) => {
    AUDIT_LOG.push({ time: new Date(now - minsAgo * 60000), actor: "Investigator (IO-114)", action, detail });
  });
  AUDIT_LOG.reverse();
})();

// ---- Data sources ------------------------------------------------------
// Buckets relationships by their evidenceSource text into the ingestion
// categories DESIGN.md specifies, so the Data Sources / Data Management pages
// show real counts derived from the dataset instead of hand-typed numbers.

const DATA_SOURCE_DEFS = [
  { key: "fir", label: "FIR / Investigation Reports", formats: "CSV · TXT · PDF", match: (s) => /FIR/i.test(s) },
  { key: "cdr", label: "Call Detail Records (CDR)", formats: "CSV", match: (s) => /CDR/i.test(s) },
  { key: "financial", label: "Financial Transactions", formats: "CSV · Excel", match: (s) => /Bank Statement|Transaction/i.test(s) },
  { key: "surveillance", label: "Surveillance Reports", formats: "CSV · TXT", match: (s) => /Surveillance/i.test(s) },
  { key: "records", label: "Official Records (KYC / RTO / Employment)", formats: "CSV · PDF", match: (s) => /KYC|Registration|Employment|subscriber record/i.test(s) },
  { key: "social", label: "Social Media Intelligence", formats: "Authorized API Request", match: (s) => /Platform metadata|Social/i.test(s) },
];

function computeDataSourceCounts(relationships) {
  const counts = DATA_SOURCE_DEFS.map((d) => Object.assign({ count: 0 }, d));
  relationships.forEach((r) => {
    const hit = counts.find((c) => c.match(r.evidenceSource || ""));
    if (hit) hit.count += 1;
  });
  return counts;
}

// ---- Sample dataset table (for the Dashboard) ---------------------------
// Synthesizes flat, spreadsheet-style rows from the graph data, mirroring the
// reference dashboard's "Sample Dataset" table. Derived from real relationship
// records rather than hand-typed, so it always matches the live graph.

function buildSampleDatasetRows(limit) {
  const rows = [];
  RELATIONSHIPS.forEach((r) => {
    const src = getEntity(r.source);
    const tgt = getEntity(r.target);
    if (!src || !tgt) return;
    const person = src.type === "person" ? src : tgt.type === "person" ? tgt : null;
    if (!person) return;
    const other = person === src ? tgt : src;
    const sourceType = /FIR/i.test(r.evidenceSource)
      ? "FIR"
      : /CDR/i.test(r.evidenceSource)
      ? "CDR"
      : /Bank Statement/i.test(r.evidenceSource)
      ? "Financial"
      : /Surveillance/i.test(r.evidenceSource)
      ? "Surveillance"
      : "Records";
    rows.push({
      recordId: rows.length + 1,
      sourceType,
      firId: /FIR/i.test(r.evidenceSource) ? r.evidenceSource : "—",
      date: r.timestamp || "—",
      personName: person.name,
      alias: person.aliases && person.aliases[0] ? person.aliases[0] : "—",
      phone: other.type === "phone" ? other.name : "—",
      location: other.type === "location" ? other.name : "—",
      organization: other.type === "organization" ? other.name : "—",
      vehicle: other.type === "vehicle" ? other.name : "—",
      transactionAmount: other.type === "transaction" ? other.name : "—",
      transactionType: other.type === "transaction" ? (other.meta && other.meta.txnType) || "—" : "—",
      description: `${person.name} ${(REL_LABELS[r.type] || r.type).toLowerCase()} ${other.name}`,
      riskScore: Math.round(investigationPriority(person.id).confidence * 100),
    });
  });
  return typeof limit === "number" ? rows.slice(0, limit) : rows;
}
