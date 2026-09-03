"""Build the TRINETRA project report PDF for mentor review."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(r"D:\Programming\claude\TriNetra\docs\TRINETRA_Project_Report.pdf")

# ---------------------------------------------------------------- palette
NAVY = colors.HexColor("#1B2A4A")
INDIGO = colors.HexColor("#3D4EA8")
ACCENT = colors.HexColor("#E07A1F")
GREEN = colors.HexColor("#1F9D63")
ROSE = colors.HexColor("#C94F7C")
GREY = colors.HexColor("#5B6478")
LIGHT = colors.HexColor("#F4F6FA")
LINE = colors.HexColor("#D7DCE7")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm

styles = getSampleStyleSheet()


def S(name, **kw):
    kw.setdefault("parent", styles["Normal"])
    return ParagraphStyle(name, **kw)


BODY = S("body", fontName="Helvetica", fontSize=9.4, leading=14.2,
         textColor=colors.HexColor("#26303F"), alignment=TA_JUSTIFY, spaceAfter=7)
BODY_L = S("bodyl", parent=BODY, alignment=0)
H1 = S("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY,
       spaceBefore=2, spaceAfter=3)
H2 = S("h2", fontName="Helvetica-Bold", fontSize=12.4, leading=16, textColor=INDIGO,
       spaceBefore=13, spaceAfter=5)
H3 = S("h3", fontName="Helvetica-Bold", fontSize=10.2, leading=13.5, textColor=NAVY,
       spaceBefore=9, spaceAfter=3)
KICKER = S("kicker", fontName="Helvetica-Bold", fontSize=8, leading=11,
           textColor=ACCENT, spaceAfter=2)
SMALL = S("small", fontName="Helvetica", fontSize=8.2, leading=11.6, textColor=GREY,
          spaceAfter=5)
CELL = S("cell", fontName="Helvetica", fontSize=8.4, leading=11.8,
         textColor=colors.HexColor("#26303F"))
CELL_B = S("cellb", parent=CELL, fontName="Helvetica-Bold", textColor=NAVY)
CELL_W = S("cellw", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")
BULLET = S("bullet", parent=BODY, leftIndent=11, bulletIndent=2, spaceAfter=3.5,
           alignment=0)


def bullets(items, style=BULLET):
    return [Paragraph(t, style, bulletText="\u2022") for t in items]


# ---------------------------------------------------------------- page frame
def decorate(canvas, doc, first=False):
    canvas.saveState()
    if first:
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 62 * mm, PAGE_W, 62 * mm, stroke=0, fill=1)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - 63.5 * mm, PAGE_W, 1.5 * mm, stroke=0, fill=1)

        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(ACCENT)
        canvas.drawString(MARGIN, PAGE_H - 19 * mm,
                          "SMART INDIA HACKATHON 2026  ·  PROBLEM STATEMENT 26189")
        canvas.setFont("Helvetica-Bold", 40)
        canvas.setFillColor(colors.white)
        canvas.drawString(MARGIN, PAGE_H - 34 * mm, "TRINETRA")
        canvas.setFont("Helvetica", 13)
        canvas.setFillColor(colors.HexColor("#C7D0E8"))
        canvas.drawString(MARGIN, PAGE_H - 43 * mm,
                          "AI-Powered Criminal Network Intelligence Platform")
        canvas.setFont("Helvetica-Oblique", 9.6)
        canvas.setFillColor(colors.HexColor("#8FA0C8"))
        canvas.drawString(MARGIN, PAGE_H - 51 * mm,
                          "Connecting Data. Revealing Networks. Empowering Investigations.")
    else:
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 13 * mm, PAGE_W, 13 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 7.6)
        canvas.setFillColor(colors.white)
        canvas.drawString(MARGIN, PAGE_H - 8.6 * mm, "TRINETRA")
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(colors.HexColor("#AEB9D4"))
        canvas.drawString(MARGIN + 21 * mm, PAGE_H - 8.6 * mm,
                          "AI-Powered Criminal Network Intelligence Platform")
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 8.6 * mm, "SIH 2026  \u00b7  PS-26189")

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 13 * mm, PAGE_W - MARGIN, 13 * mm)
    canvas.setFont("Helvetica", 7.2)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN, 9 * mm, "Prototype report \u00b7 All data synthetic")
    canvas.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(path, pagesize=A4,
                         leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN, bottomMargin=MARGIN,
                         title="TRINETRA - Prototype Report",
                         author="Team TRINETRA",
                         subject="SIH 2026 PS-26189 project report")
        cover = Frame(MARGIN, 18 * mm, PAGE_W - 2 * MARGIN, PAGE_H - 82 * mm, id="cover")
        body = Frame(MARGIN, 17 * mm, PAGE_W - 2 * MARGIN, PAGE_H - 34 * mm, id="body")
        self.addPageTemplates([
            PageTemplate(id="Cover", frames=[cover],
                         onPage=lambda c, d: decorate(c, d, first=True)),
            PageTemplate(id="Body", frames=[body], onPage=decorate),
        ])


# ---------------------------------------------------------------- helpers
def kv_table(rows, widths, header=None, zebra=True):
    data = []
    if header:
        data.append([Paragraph(h, CELL_W) for h in header])
    for r in rows:
        data.append([Paragraph(str(c), CELL_B if i == 0 and not header else CELL)
                     for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), INDIGO),
                  ("LINEBELOW", (0, 0), (-1, 0), 0, colors.white)]
    if zebra:
        start = 1 if header else 0
        for i in range(start, len(data)):
            if (i - start) % 2 == 1:
                style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(style))
    return t


def stat_row(items):
    """A row of headline numbers."""
    cells = []
    for value, label in items:
        cells.append([Paragraph(f'<font size="15" color="#3D4EA8"><b>{value}</b></font>', CELL),
                      Paragraph(label, SMALL)])
    data = [[c[0] for c in cells], [c[1] for c in cells]]
    w = (PAGE_W - 2 * MARGIN) / len(items)
    t = Table(data, colWidths=[w] * len(items), hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, LINE),
    ]))
    return t


def callout(title, text, colour=ACCENT):
    inner = [Paragraph(title, S("ct", fontName="Helvetica-Bold", fontSize=9,
                                leading=12, textColor=colour, spaceAfter=3)),
             Paragraph(text, S("cb", parent=BODY, fontSize=8.8, leading=12.6, spaceAfter=0))]
    t = Table([[inner]], colWidths=[PAGE_W - 2 * MARGIN], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, colour),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def bar_chart(rows, maxv, width=PAGE_W - 2 * MARGIN, colour=INDIGO):
    """Horizontal bars drawn as a table - avoids image dependencies."""
    data = []
    for label, value in rows:
        frac = value / maxv if maxv else 0
        bar_w = max(1.0, frac * (width * 0.52))
        bar = Table([[""]], colWidths=[bar_w], rowHeights=[7])
        bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colour),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        data.append([Paragraph(label, CELL), bar,
                     Paragraph(f"<b>{value:,}</b>", CELL)])
    t = Table(data, colWidths=[width * 0.27, width * 0.56, width * 0.17], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    return t


# ================================================================ content
story = []
A = story.append

# ---------------------------------------------------------------- COVER
A(Paragraph("Prototype Report", H1))
A(Paragraph(
    "A working full-stack platform, deployed and publicly accessible. This report "
    "describes what has been built, how each analytical claim is produced, what is "
    "genuinely novel about the approach, and - equally important - what is not yet "
    "connected. It is written for technical review.", BODY))
A(Spacer(1, 4 * mm))

A(kv_table([
    ["Organisation", "Ministry of Home Affairs \u00b7 National Crime Records Bureau \u00b7 Women Safety Division"],
    ["Problem", "AI-Powered Criminal Network Analysis System (PS-26189)"],
    ["Category / Theme", "Software \u00b7 Blockchain &amp; Cybersecurity"],
    ["Live deployment", '<font color="#3D4EA8"><b>https://trinetra-rosy-gamma.vercel.app</b></font>'],
    ["Source", "github.com/Ayush052007/trinetra"],
    ["Status", "Deployed \u00b7 124 automated checks passing \u00b7 all data synthetic"],
], widths=[36 * mm, PAGE_W - 2 * MARGIN - 36 * mm], zebra=True))

A(Spacer(1, 6 * mm))
A(callout(
    "One sentence",
    "TRINETRA turns fragmented investigative records into a queryable knowledge graph, "
    "surfaces connections that siloed records hide, and puts every AI-derived finding in "
    "front of an authorised investigator before it can enter a case record - because it "
    "is a decision-support system, not a verdict machine.",
    INDIGO))

A(NextPageTemplate("Body"))
A(PageBreak())

# ---------------------------------------------------------------- 1
A(Paragraph("1.  The problem, and why it is hard", H1))
A(Paragraph(
    "Investigative data arrives fragmented. A phone number sits in a call-detail record, "
    "a vehicle in an RTO extract, a name in an FIR filed in a different district, a "
    "payment in a bank statement. Each record is individually unremarkable. The "
    "connection between them is what matters, and it is precisely what no single record "
    "contains.", BODY))
A(Paragraph(
    "The problem statement asks for a system that collects multi-source data, extracts "
    "entities, builds relationship maps, identifies influential individuals, detects "
    "suspicious patterns, and gives investigators visual and analytical insight. The "
    "difficulty is not any one of those in isolation - it is doing all of them while "
    "remaining <b>defensible</b>. An investigative tool that produces a confident number "
    "nobody can explain is worse than no tool at all: it launders a guess into apparent "
    "evidence.", BODY))

A(Paragraph("Two design commitments", H3))
A(Paragraph(
    "Everything in this build follows from two rules we set before writing code:", BODY))
story += bullets([
    "<b>If it is displayed, it is computed.</b> No button that only prints a message, no "
    "chart with hardcoded values, no page pretending to be connected to a backend. Every "
    "figure in the interface comes from a query or an algorithm run against stored data.",
    "<b>Observed and inferred are never confused.</b> The distinction lives in the "
    "database schema, not in UI styling, so no view can accidentally present a derived "
    "link as a recorded fact. Every inferred connection carries its confidence, its "
    "reason, and the specific records that produced it.",
])

A(callout(
    "Why this matters more than the feature list",
    "A platform that identifies a person as a suspect makes a claim about a human being. "
    "TRINETRA never does that. It produces an <b>Investigation Priority Score</b> - an "
    "analytical triage signal that ranks where investigator attention is likely to be "
    "productive - and it shows the seven weighted factors and the underlying records "
    "behind every score. The word 'guilt' does not appear anywhere in the system.", ROSE))

# ---------------------------------------------------------------- 2
A(Paragraph("2.  What has actually been built", H2))
A(Paragraph(
    "This is a deployed, working system rather than a screen-flow prototype. The figures "
    "below are counted from the codebase and the live database, not estimated.", BODY))
A(Spacer(1, 2 * mm))
A(stat_row([("21,113", "lines of code"), ("67", "API endpoints"),
            ("30", "database tables"), ("124", "automated checks")]))
A(Spacer(1, 3 * mm))
A(stat_row([("3,117", "entities"), ("8,511", "relationships"),
            ("8,452", "source records"), ("426", "safety incidents")]))
A(Spacer(1, 5 * mm))

A(Paragraph("2.1  Investigation capabilities", H3))
A(kv_table([
    ["Authentication", "scrypt password hashing, JWT access tokens with rotating refresh "
     "tokens, account lockout after 5 failed attempts, session expiry, full audit trail"],
    ["Access control", "5 roles with granular permissions, enforced by the backend on "
     "every endpoint - a lower-privileged role genuinely receives 403, not a hidden button"],
    ["Dashboard", "9 widgets, each computed live and each a doorway into its detail page "
     "with the relevant filter already applied"],
    ["Knowledge graph", "1/2/3-hop expansion, shortest path, common connections, type "
     "filtering; observed edges solid, inferred edges dashed"],
    ["Graph analytics", "Degree, betweenness and closeness centrality; Louvain community "
     "detection; connected components"],
    ["Hidden links", "Adamic-Adar weighted link prediction, each result carrying its "
     "reason, supporting records and confidence"],
    ["Entity resolution", "Multi-signal alias matching with per-factor scoring; nothing "
     "merges without an investigator decision"],
    ["AI / NLP", "Entity and relationship extraction from unstructured text, anchored to "
     "character spans so the interface highlights the exact words responsible"],
    ["Ingestion", "Validate, parse, clean, normalise, deduplicate, extract, resolve, "
     "relate, store, update graph - counters computed from the uploaded file"],
    ["Reporting", "Case reports compiled from stored data to HTML, real PDF and JSON, "
     "each carrying an explicit analytical disclaimer"],
], widths=[32 * mm, PAGE_W - 2 * MARGIN - 32 * mm]))

A(Paragraph("2.2  Women Safety Intelligence module", H3))
A(Paragraph(
    "Built as a first-class part of the same platform rather than a separate application. "
    "A safety incident references the same entity table as the criminal network, which is "
    "what allows a harassment report to be pivoted directly into the network graph and "
    "checked against repeat-offender history across districts.", BODY))
A(kv_table([
    ["SOS", "One-tap alert with a real backend workflow: RECEIVED \u2192 ASSIGNED \u2192 "
     "RESPONDING \u2192 RESOLVED. Forward-only transitions, full status history, dispatcher "
     "console. Never claims an emergency call was placed."],
    ["Safety heatmap", "Green / Yellow / Orange / Red computed by severity-weighted kernel "
     "density over stored incidents, recoloured on every filter change"],
    ["AI Safe Route", "Yen's k-shortest paths over a waypoint graph whose cost blends "
     "distance, incident density, recent alerts, time of day, lighting and emergency-service "
     "proximity - with a per-factor score breakdown"],
    ["Suspicious patterns", "Cross-incident clustering on shared vehicles, devices, "
     "locations and entities, linked back into the network graph"],
    ["Repeated encounters", "Co-occurrence scoring across person, vehicle, location, time "
     "and device within spatial-temporal windows, citing the actual events that produced it"],
    ["Nearby services", "Police, hospitals, response units and safe locations by real "
     "distance calculation"],
    ["Live alerts", "WebSocket feed with automatic polling fallback"],
], widths=[32 * mm, PAGE_W - 2 * MARGIN - 32 * mm]))

A(Spacer(1, 3 * mm))
A(callout(
    "Language discipline in the safety module",
    "Repeated-encounter detection is always worded as a <i>potential pattern requiring "
    "authorised investigator review</i>. The system never labels a person a stalker. This "
    "is a deliberate constraint: the same detection logic, worded carelessly, would be an "
    "accusation generator.", ROSE))

# ---------------------------------------------------------------- 3
A(Paragraph("3.  Technical analysis", H2))
A(Paragraph("3.1  Architecture", H3))
A(Paragraph(
    "A single Python service with no mandatory external dependencies. The relational "
    "store is the system of record; the graph is a queryable projection of it, which "
    "prevents the two from drifting apart.", BODY))
A(kv_table([
    ["Frontend", "React 18 with hooks and context, served as static files. 22 modules, "
     "6,984 lines"],
    ["Backend", "FastAPI on Python 3.12+, 67 endpoints, 40 modules, 10,724 lines"],
    ["Data", "SQLAlchemy 2.0 over PostgreSQL (deployed) or SQLite (local) - same code"],
    ["Graph", "A repository interface with two real implementations: an in-process "
     "pure-Python engine and a Neo4j/Cypher adapter, selected by configuration"],
    ["AI", "trinetra_nlp (extraction) and trinetra_er (resolution), 1,298 lines"],
    ["Deployment", "Vercel serverless + Neon PostgreSQL, HTTPS, publicly reachable"],
], widths=[26 * mm, PAGE_W - 2 * MARGIN - 26 * mm]))

A(Paragraph("3.2  The algorithms are real, and they are exact", H3))
A(Paragraph(
    "Every analytical function is deterministic: the same graph produces the same output "
    "on every run. This is not incidental - an investigator must be able to re-derive any "
    "figure the platform showed them, potentially months later in a courtroom.", BODY))
story += bullets([
    "<b>Brandes' betweenness centrality</b> identifies brokers - entities sitting on paths "
    "between otherwise disconnected parts of a network. Often more investigatively "
    "interesting than raw degree, because a broker's removal fragments the network.",
    "<b>Louvain community detection</b> with modularity scoring, to find clusters.",
    "<b>Yen's k-shortest paths</b> for genuinely distinct route alternatives, not one path "
    "plus arbitrary detours.",
    "<b>Adamic-Adar link prediction</b>, which weights shared connections by how rare they "
    "are: a contact who knows only two people is far more telling than a hub who knows hundreds.",
])
A(Paragraph(
    "Where an exact computation would be too slow inside a web request, the system says so "
    "rather than hiding it. Exact betweenness on a 3,117-node graph runs for over a minute "
    "in pure Python, so the platform switches to the seeded Brandes-Pich estimator and "
    "<b>labels the output as estimated</b>, naming the number of pivots used.", BODY))

A(Paragraph("3.3  Composition of the knowledge graph", H3))
A(Paragraph("Entity population by type, from the live database:", SMALL))
A(bar_chart([("Person", 1202), ("Phone", 1008), ("Transaction", 392),
             ("Vehicle", 294), ("Organization", 194), ("Location", 28)], 1202))
A(Spacer(1, 4 * mm))
A(Paragraph("Relationship population by type:", SMALL))
A(bar_chart([("Visited", 2240), ("Associated with", 1373), ("Owned", 1367),
             ("Called", 987), ("Met", 951), ("Worked for", 646),
             ("Transferred money", 391)], 2240, colour=ACCENT))
A(Spacer(1, 4 * mm))
A(Paragraph("Women-safety incidents by category:", SMALL))
A(bar_chart([("Harassment", 135), ("Suspicious contact", 75), ("Stalking", 70),
             ("Threat", 52), ("Suspicious vehicle", 38), ("Assault", 35),
             ("Missing person", 9)], 135, colour=ROSE))

A(Spacer(1, 5 * mm))
A(Paragraph("3.4  Investigation Priority Score distribution", H3))
A(Paragraph(
    "Scores are computed for all 3,117 entities from seven weighted factors. The "
    "distribution is heavily skewed toward LOW, which is the intended behaviour: a triage "
    "signal that marked everything as high priority would be useless. One entity reaches "
    "CRITICAL, 286 reach HIGH.", BODY))
A(kv_table([
    ["LOW", "1,568", "Routine - no elevated structural signal"],
    ["MEDIUM", "1,262", "Some connectivity or activity worth noting"],
    ["HIGH", "286", "Multiple converging factors - review recommended"],
    ["CRITICAL", "1", "Strong convergence across most factors"],
], widths=[24 * mm, 22 * mm, PAGE_W - 2 * MARGIN - 46 * mm],
    header=["Band", "Count", "Interpretation"]))

# ---------------------------------------------------------------- 4
A(Paragraph("4.  What is innovative here", H2))
A(Paragraph(
    "Graph visualisation of criminal networks is not new; commercial tools do it well. "
    "The contributions below are where this build differs from both those tools and from "
    "a typical hackathon entry.", BODY))

A(Paragraph("4.1  Evidence status as a schema-level primitive", H3))
A(Paragraph(
    "Most systems distinguish observed from inferred data in the presentation layer, if at "
    "all. Here every relationship carries an <b>evidence_status</b> column "
    "(OBSERVED / INFERRED / UNDER_REVIEW / VALIDATED / REJECTED) plus a "
    "<b>derivation</b> field holding the ids of the records that produced it. Because the "
    "distinction is structural, a filter for 'observed only' genuinely removes inferred "
    "edges from traversal - it is not a colour change. The knowledge graph will answer "
    "'what do we actually know?' as a different question from 'what do we suspect?'", BODY))

A(Paragraph("4.2  Identifier-strength entity resolution", H3))
A(Paragraph(
    "Standard record linkage weights name similarity heavily. That fails on the exact case "
    "that matters most: an alias is <i>expected</i> to have a different name. Our resolver "
    "found that two records sharing a vehicle registration and an ID-proof reference - "
    "near-conclusive evidence - scored below threshold purely because the names differed.", BODY))
A(Paragraph(
    "The fix was to model identifier strength explicitly. A shared ID proof (0.80), device "
    "identifier (0.78), vehicle registration (0.75) or phone (0.72) each establishes a "
    "<b>minimum confidence floor</b> independent of name similarity, recorded as its own "
    "visible factor. On the demonstration case this produces a 0.86 confidence alias link "
    "between two identities across separate district FIRs - derived from shared "
    "identifiers, not hardcoded. Meanwhile two unrelated people sharing a common surname "
    "and nothing else score 0.31 and are correctly filtered out.", BODY))

A(callout(
    "The guard that matters",
    "Name similarity alone is capped: without corroboration from a shared identifier, "
    "connection or case, a pair cannot reach high confidence no matter how identical the "
    "names. In a country where surnames are widely shared, the alternative would generate "
    "false alias links at scale.", GREEN))

A(Paragraph("4.3  Span-anchored, inspectable NLP", H3))
A(Paragraph(
    "Extraction records the exact character offsets that produced each entity, so the "
    "interface highlights the specific words responsible. A reviewer can always ask "
    "\u2018which text produced this?\u2019 and get an exact answer rather than a plausible "
    "summary. The pipeline is deterministic and rule-based - regex recognisers for Indian "
    "phone, vehicle-registration, currency and FIR-identifier formats, a gazetteer that "
    "grows as the graph does, and trigger-verb relation extraction.", BODY))
A(Paragraph(
    "Two refinements came from testing against the project's own case text. Case files "
    "drop to a first name after introducing someone, so the gazetteer resolves unambiguous "
    "name parts - but refuses when two people share one. And money flows have a three-part "
    "shape (payer, amount, payee), so pairing the payer with only the nearest entity "
    "captured the amount and lost the recipient, which is the investigatively interesting "
    "half.", BODY))

A(Paragraph("4.4  Women Safety as graph intelligence, not a separate app", H3))
A(Paragraph(
    "The module shares the entity table with the criminal network. That is the point: a "
    "harassment complaint becomes a graph query against repeat-offender history across "
    "district boundaries. The demonstration case shows exactly this - a stalking complaint "
    "resolving, through a SIM purchase record and a vehicle registration, to a prior FIR "
    "filed in a different district that the two siloed systems would never have connected.", BODY))

A(Paragraph("4.5  Deployability as a design constraint", H3))
A(Paragraph(
    "The platform runs with no external services: pure-Python graph algorithms, stdlib "
    "password hashing, SQLite by default. That is not a limitation but a deliberate "
    "property - it deploys to a free tier, an offline demonstration machine, or a district "
    "office with poor connectivity. PostgreSQL and Neo4j are configuration changes, not "
    "rewrites, because both sit behind interfaces with two real implementations.", BODY))

# ---------------------------------------------------------------- 5
A(Paragraph("5.  Verification", H2))
A(Paragraph(
    "124 automated checks pass: 63 unit and API tests, plus 61 end-to-end assertions "
    "against a running server. The end-to-end suite deliberately tests the claims that "
    "would be easiest to fake.", BODY))
A(kv_table([
    ["Dashboard figures match a direct database query", "Rules out hardcoded display values"],
    ["A lower-privileged role receives 403 from the server", "Proves RBAC is enforced, not cosmetic"],
    ["An investigator decision changes stored state", "Proves validation is real, not visual"],
    ["The SOS workflow refuses illegal transitions", "Proves the state machine exists"],
    ["A re-uploaded file is deduplicated", "Proves content hashing works"],
    ["Data survives a server restart", "Proves persistence, not in-memory state"],
], widths=[PAGE_W - 2 * MARGIN - 62 * mm, 62 * mm],
    header=["Assertion", "What it rules out"]))

A(Spacer(1, 3 * mm))
A(Paragraph(
    "All 24 interface pages were swept in a browser and render with zero errors and zero "
    "stuck loading states, most within 200ms.", BODY))

# ---------------------------------------------------------------- 6
A(Paragraph("6.  Honest limitations", H2))
A(Paragraph(
    "This section exists because a mentor will ask, and because a project that overstates "
    "itself is easy to dismantle in review.", BODY))
A(kv_table([
    ["All data is synthetic", "Both demonstration cases and the generated background "
     "population are fictional. Every row carries a data classification and the banner "
     "stays visible until a deployment loads authorised data."],
    ["No external integrations are live", "Device GPS, emergency dispatch, telecom CDR "
     "feeds, RTO lookup and CCTNS sync are structured with defined interfaces but marked "
     "REQUIRES AUTHORISATION. Nothing pretends to be connected."],
    ["NLP is rule-based", "Deterministic and fully inspectable, but it does not claim "
     "model-level recall on free prose. A transformer or spaCy pipeline can be substituted "
     "through the existing engine interface."],
    ["Neo4j adapter is untested live", "A complete Cypher implementation with constraints "
     "and indexes, but no Neo4j instance was available to exercise it. The embedded engine "
     "is the tested path."],
    ["Serverless trade-offs", "On the current deployment, WebSocket live updates fall back "
     "to polling and cross-instance broadcast is unreliable. A conventional server has "
     "neither limitation."],
    ["Demo credentials are shared", "The deployed instance uses one password across "
     "accounts because per-account files do not survive an ephemeral filesystem. "
     "Acceptable only for synthetic data; a real deployment needs individually issued "
     "credentials and MFA."],
], widths=[42 * mm, PAGE_W - 2 * MARGIN - 42 * mm]))

# ---------------------------------------------------------------- 7
A(Paragraph("7.  Suggested demonstration path", H2))
A(Paragraph(
    "Roughly five minutes, and it exercises the claims that distinguish this build.", BODY))
A(kv_table([
    ["1", "Sign in as IO-114. The top bar shows the officer's name, service ID, role and "
     "unit - identity is real, not a placeholder."],
    ["2", "From the dashboard, click any KPI tile. It opens the detail page with the "
     "filter already applied. Every widget is a doorway."],
    ["3", "Search Rahul Sharma \u2192 profile \u2192 Explore Network \u2192 expand to 2 hops."],
    ["4", "Open a dashed (inferred) edge \u2192 View Evidence. It shows the supporting "
     "records and confidence \u2192 Validate. The status changes in the database, the graph, "
     "the dashboard and the audit log simultaneously."],
    ["5", "Entity Resolution: the S1 \u2194 S2 alias candidate at 0.86 with its factor "
     "breakdown. Accept it and watch the merge record appear."],
    ["6", "AI &amp; NLP: paste FIR text, run extraction, note that the source words are "
     "highlighted for each entity found."],
    ["7", "Women Safety: raise an SOS and move it through the response workflow. Then the "
     "heatmap - change the incident-type filter and watch zones recolour from live data."],
    ["8", "Safe Route LOC1 \u2192 LOC2: three ranked routes, each with a score breakdown."],
    ["9", "Sign in as AN-331 (Analyst) and attempt to validate a relationship. The server "
     "returns 403 - the permission boundary is real."],
], widths=[10 * mm, PAGE_W - 2 * MARGIN - 10 * mm]))

# ---------------------------------------------------------------- 8
A(Paragraph("8.  Where this goes next", H2))
A(kv_table([
    ["Near term", "Exercise the Neo4j adapter against a live instance; substitute a "
     "transformer NER model behind the existing interface and measure the difference; "
     "move live updates onto a shared queue so broadcast works under serverless"],
    ["Pilot readiness", "Individually issued credentials with MFA; per-district data "
     "partitioning; retention and purge policy; a formal review of the priority-score "
     "factor weights with investigating officers"],
    ["Integration", "Authorised connections to CCTNS, telecom CDR feeds and RTO lookup - "
     "each already has a defined interface and data contract awaiting authorisation"],
    ["Evaluation", "The honest gap: we can demonstrate that the analytics are correct and "
     "reproducible, but not yet that they improve investigative outcomes. That needs a "
     "supervised pilot with real officers and measured against real case closure."],
], widths=[34 * mm, PAGE_W - 2 * MARGIN - 34 * mm]))

A(Spacer(1, 5 * mm))
A(callout(
    "Closing position",
    "TRINETRA is a working investigative decision-support platform, deployed and testable "
    "today, in which every analytical claim can be traced to the records that produced it. "
    "It does not determine guilt, it does not replace human judgement, and it states "
    "clearly what it cannot yet do. We think that combination - genuinely functional and "
    "genuinely honest about its limits - is the right thing to bring to a problem where "
    "being wrong has consequences for real people.", INDIGO))

A(Spacer(1, 6 * mm))
A(Paragraph(
    "<b>Live platform:</b> https://trinetra-rosy-gamma.vercel.app &nbsp;\u00b7&nbsp; "
    "<b>Source:</b> github.com/Ayush052007/trinetra<br/>"
    "Sign in with a Service ID (IO-114, WSO-052, ADM-001) - not an email address.", SMALL))

Doc(str(OUT)).build(story)
print(f"written: {OUT}")
print(f"size: {OUT.stat().st_size:,} bytes")
