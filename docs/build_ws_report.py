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

OUT = Path(r"D:\Programming\claude\TriNetra\docs\TRINETRA_Women_Safety_Report.pdf")

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
        canvas.drawString(MARGIN, PAGE_H - 33 * mm, "TRINETRA")
        canvas.setFont("Helvetica", 13)
        canvas.setFillColor(colors.HexColor("#C7D0E8"))
        canvas.drawString(MARGIN, PAGE_H - 43 * mm,
                          "Women Safety Intelligence Module")
        canvas.setFont("Helvetica-Oblique", 9.6)
        canvas.setFillColor(colors.HexColor("#8FA0C8"))
        canvas.drawString(MARGIN, PAGE_H - 51 * mm,
                          "Connecting complaints. Revealing patterns. Protecting people.")
    else:
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 13 * mm, PAGE_W, 13 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 7.6)
        canvas.setFillColor(colors.white)
        canvas.drawString(MARGIN, PAGE_H - 8.6 * mm, "TRINETRA")
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(colors.HexColor("#AEB9D4"))
        canvas.drawString(MARGIN + 21 * mm, PAGE_H - 8.6 * mm,
                          "Women Safety Intelligence Module")
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 8.6 * mm, "SIH 2026  \u00b7  PS-26189")

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 13 * mm, PAGE_W - MARGIN, 13 * mm)
    canvas.setFont("Helvetica", 7.2)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN, 9 * mm, "Women Safety module \u00b7 All data synthetic")
    canvas.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(path, pagesize=A4,
                         leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN, bottomMargin=MARGIN,
                         title="TRINETRA - Women Safety Intelligence Report",
                         author="Team TRINETRA",
                         subject="Women Safety Intelligence module - technical report")
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
A(Paragraph("Women Safety Intelligence", H1))
A(Paragraph(
    "A module of the TRINETRA platform, built for the division that issued this "
    "problem statement. This report covers what the module does, the algorithms "
    "behind each figure it displays, what makes the approach different, and the "
    "limits we have deliberately placed on it.", BODY))
A(Spacer(1, 4 * mm))

A(kv_table([
    ["Issued by", "Ministry of Home Affairs · National Crime Records Bureau · "
     "<b>Women Safety Division</b>"],
    ["Problem", "AI-Powered Criminal Network Analysis System (PS-26189)"],
    ["Module status", "Built, deployed and publicly accessible"],
    ["Live deployment", '<font color="#3D4EA8"><b>https://trinetra-rosy-gamma.vercel.app</b></font>'],
    ["Sign in as", "Service ID <b>WSO-052</b> (Women Safety Officer)"],
    ["Demonstration case", "DEMO/WS-2026-0417 — Stalking &amp; Harassment Investigation"],
    ["Data classification", "Synthetic throughout · no real person or incident"],
], widths=[34 * mm, PAGE_W - 2 * MARGIN - 34 * mm]))

A(Spacer(1, 5 * mm))
A(callout(
    "Why this module exists",
    "Crimes against women are frequently preceded by a pattern - repeated calls, a "
    "vehicle seen twice, a complaint filed and closed. Each report, read alone, looks "
    "minor. Today those reports live in separate files, separate stations, sometimes "
    "separate districts, and the pattern is invisible until it escalates. This module "
    "exists to make that pattern visible while it still matters.", ROSE))

A(NextPageTemplate("Body"))
A(PageBreak())

# ---------------------------------------------------------------- 1
A(Paragraph("1.  The need", H1))
A(Paragraph(
    "Delhi recorded <b>13,366</b> crimes against women in 2023 - the highest of any "
    "Indian metro - including roughly 4,000 cases of kidnapping and abduction of women "
    "and girls. Police commentary attributes recent declines partly to night patrolling "
    "and mobile women-police teams, but sustained reduction depends on something those "
    "measures cannot provide: <b>identifying repeat offenders and linking cases across "
    "jurisdictions</b>.", BODY))
A(Paragraph(
    "That is the specific gap this module targets. Not more reporting channels - India "
    "has those - but making the reports that already exist speak to each other.", BODY))
A(Paragraph(
    "<i>Figures above are real, publicly reported NCRB and Delhi Police data, cited via "
    "Deccan Herald and The Tribune. They are stored in the platform under a separate "
    "REFERENCE classification and are never mixed into any analytical computation.</i>",
    SMALL))

A(Paragraph("1.1  The structural problem", H3))
A(Paragraph(
    "A harassment complaint is filed at Station A. Three months later, a stalking "
    "complaint naming a different alias is filed at Station B in another district. The "
    "same vehicle appears in both. Under current practice nothing connects them, because "
    "connecting them would require an officer to have read both files and remembered a "
    "partial registration number. TRINETRA makes that link a database query rather than "
    "an act of memory.", BODY))

# ---------------------------------------------------------------- 2
A(Paragraph("2.  What the module does", H2))
A(Paragraph(
    "Seven capabilities, all working against live stored data through 16 dedicated API "
    "endpoints. Figures below are counted from the deployed database.", BODY))
A(Spacer(1, 2 * mm))
A(stat_row([("426", "incidents recorded"), ("23", "SOS alerts handled"),
            ("26", "safety alerts"), ("3", "patterns detected")]))
A(Spacer(1, 3 * mm))
A(stat_row([("5", "safety zones"), ("6", "emergency services"),
            ("11", "routing waypoints"), ("16", "safety endpoints")]))
A(Spacer(1, 5 * mm))

A(kv_table([
    ["SOS Response Console", "One-tap alert with an enforced response workflow, auto-routed "
     "to the nearest zone, with emergency contacts pulled from the record"],
    ["Safety Heatmap", "Zone risk bands computed live from incident density, recoloured on "
     "every filter change"],
    ["AI Safe Route", "Ranked route alternatives scored on six safety factors, each shown "
     "to the user"],
    ["Suspicious Pattern Detection", "Cross-incident clustering on shared vehicles, devices, "
     "locations and people"],
    ["Repeated-Encounter Detection", "Co-occurrence scoring across person, vehicle, location, "
     "time and device"],
    ["Nearby Services", "Police, hospitals, response units and safe locations by real distance"],
    ["Live Safety Alerts", "Prioritised feed with a response-status workflow"],
], widths=[46 * mm, PAGE_W - 2 * MARGIN - 46 * mm]))

# ---------------------------------------------------------------- 3
A(Paragraph("3.  How each figure is produced", H2))
A(Paragraph(
    "Nothing in this module is a placeholder value. Each section below states the actual "
    "computation, because a safety figure an investigator cannot interrogate is a figure "
    "they should not act on.", BODY))

A(Paragraph("3.1  SOS Response Console", H3))
A(Paragraph(
    "Raising an SOS triggers three automatic actions: the <b>nearest safety zone</b> is "
    "computed by haversine distance against every zone centroid; the subject's "
    "<b>registered emergency contacts</b> are retrieved in priority order and logged; and "
    "a linked entry is pushed to the operations alert feed.", BODY))
A(Paragraph("The alert then moves through an <b>enforced state machine</b>:", BODY))
A(kv_table([
    ["RECEIVED", "Logged by the console. Awaiting assignment."],
    ["ASSIGNED", "A response unit and officer are attached. Officer identity recorded."],
    ["RESPONDING", "Unit en route."],
    ["RESOLVED", "Closed, with resolution timestamp."],
], widths=[30 * mm, PAGE_W - 2 * MARGIN - 30 * mm], header=["State", "Meaning"]))
A(Spacer(1, 2 * mm))
A(Paragraph(
    "Transitions are validated <b>server-side</b>. An attempt to jump from RECEIVED "
    "straight to RESOLVED is rejected with an error naming the permitted next states. "
    "Every transition writes an immutable history row recording the previous state, the "
    "new state, the officer, the timestamp and an optional note - so elapsed response "
    "time is a matter of record rather than recollection.", BODY))

A(callout(
    "What it does not do",
    "Raising an SOS notifies the in-platform operations console only. It does not place "
    "an emergency call, and the interface never implies otherwise. Location is labelled "
    "SIMULATED unless a device GPS source is configured, so an officer always knows "
    "whether a position is a real fix. Building the dispatcher workflow honestly was "
    "preferred to simulating a capability we do not have authorisation for.", ACCENT))

A(Paragraph("3.2  Safety Heatmap", H3))
A(Paragraph(
    "Each zone's band comes from a <b>severity-weighted Gaussian kernel density</b>. "
    "Incidents are weighted by priority, then attenuated by distance from the zone "
    "centre - an incident at the centre counts fully, one near the boundary counts "
    "little - and divided by zone area to give incidents per square kilometre.", BODY))
A(kv_table([
    ["Severity weights", "LOW 1.0 · MEDIUM 2.0 · HIGH 3.5 · CRITICAL 5.0"],
    ["Band thresholds", "RED ≥ 12.0 · ORANGE ≥ 6.0 · YELLOW ≥ 2.0 · "
     "GREEN below 2.0 (weighted incidents per km²)"],
    ["Filters", "Incident type, severity, time of day, reporting period"],
], widths=[32 * mm, PAGE_W - 2 * MARGIN - 32 * mm]))
A(Spacer(1, 2 * mm))
A(callout(
    "A deliberate wording constraint",
    "A band describes <b>reporting density</b> - not danger, and not the people who live "
    "in an area. Areas with better reporting culture can appear worse than areas where "
    "victims do not come forward, and a tool that labelled the latter 'safe' would be "
    "actively harmful. The absolute weighted density is always shown next to the band so "
    "the underlying figure is visible, and the interface states this limitation on screen.",
    ROSE))

A(Paragraph("3.3  AI Safe Route", H3))
A(Paragraph(
    "Routes are computed with <b>Yen's k-shortest paths</b> over a waypoint graph of 11 "
    "nodes and 30 segments, giving genuinely distinct alternatives rather than one path "
    "with detours. The cost of each segment is not distance alone:", BODY))
A(kv_table([
    ["Incident density", "Weighted incident pressure around the segment midpoint (+22% per unit)"],
    ["Street lighting", "Unlit segments penalised by 30%"],
    ["Recent alerts", "Segments in zones with unresolved alerts penalised by 25%"],
    ["Time of day", "Multiplier applied for late-night travel"],
    ["Emergency proximity", "Distance to the nearest police station, hospital or response unit"],
    ["Distance", "Base haversine distance of the segment"],
], widths=[38 * mm, PAGE_W - 2 * MARGIN - 38 * mm], header=["Factor", "Effect on route cost"]))
A(Spacer(1, 2 * mm))
A(Paragraph(
    "Every returned route carries its <b>per-factor breakdown</b> - how many segments were "
    "unlit, how many crossed alert zones, average distance to emergency services - so the "
    "recommendation can be inspected rather than trusted. Wording is deliberately hedged: "
    "<i>recommended based on available safety indicators</i>, never 'this route is safe'.", BODY))

A(Paragraph("3.4  Repeated-Encounter Detection", H3))
A(Paragraph(
    "This is the module's most sensitive analysis and carries the most constraints. It "
    "scores co-occurrence between a subject and another entity - a person, a vehicle, a "
    "phone or device - across <b>distinct days and distinct locations</b>, weighted for "
    "escalation trend. A pattern is only surfaced when it spans at least two locations or "
    "two separate days: a single co-occurrence is a coincidence, not a pattern.", BODY))
A(Paragraph(
    "Output names the <b>actual supporting events</b> - the specific dates and locations "
    "that produced the finding - so an officer verifies the underlying records rather than "
    "the score. Findings are always worded as a <i>potential repeated-encounter pattern "
    "requiring authorised investigator review</i>. The system never labels a person a "
    "stalker; the same logic, worded carelessly, would be an accusation generator.", BODY))

A(Paragraph("3.5  Suspicious Pattern Detection", H3))
A(Paragraph(
    "Clusters incidents that share a vehicle descriptor, device identifier, location or "
    "named entity, across cases and across stations. Each detection stores its supporting "
    "incidents, events and entities, and an <b>Investigate Connection</b> action opens the "
    "network graph seeded with exactly that subgraph - moving the officer from a safety "
    "complaint into full network analysis in one click.", BODY))

# ---------------------------------------------------------------- 4
A(Paragraph("4.  Incident composition", H2))
A(Paragraph("Recorded incidents by category, from the deployed database:", SMALL))
A(bar_chart([("Harassment", 135), ("Suspicious contact", 75), ("Stalking", 70),
             ("Threat", 52), ("Suspicious vehicle", 38), ("Assault / confrontation", 35),
             ("Other", 12), ("Missing person", 9)], 135, colour=ROSE))
A(Spacer(1, 3 * mm))
A(Paragraph(
    "The distribution is deliberate. Harassment and suspicious contact dominate because "
    "those are the early-stage signals the module is designed to catch - the reports that "
    "are individually minor and collectively meaningful. Assault appears rarely, which is "
    "the outcome the pattern detection is meant to pre-empt.", BODY))

# ---------------------------------------------------------------- 5
A(Paragraph("5.  What is different about this approach", H2))

A(Paragraph("5.1  It is not a separate application", H3))
A(Paragraph(
    "The module shares the same entity table as the criminal network side. A safety "
    "incident references the same person, phone and vehicle records used in financial or "
    "network investigations. That is the entire point: a harassment complaint becomes a "
    "graph query against repeat-offender history, automatically, across district "
    "boundaries. Most safety applications are complaint registries that cannot do this "
    "because their data lives in isolation.", BODY))

A(Paragraph("5.2  The demonstration case shows the mechanism", H3))
A(Paragraph(
    "Case DEMO/WS-2026-0417 traces a stalking complaint through to a prior FIR filed in a "
    "different district under a different name. The chain is entirely evidential: an "
    "unregistered number, correlated by call pattern to a SIM purchase record, whose KYC "
    "ID proof matches the suspect, who is the registered owner of a vehicle sighted twice "
    "at the victim's residence and once at the confrontation site. Entity resolution then "
    "links that identity to a prior stalking FIR at <b>0.86 confidence</b> - a figure "
    "derived from shared identifiers, not hardcoded.", BODY))
A(Paragraph("Two siloed district systems would never have connected those files.", BODY))

A(Paragraph("5.3  Every alert is traceable", H3))
A(Paragraph(
    "Safety alerts store a <b>supporting</b> field holding the record identifiers behind "
    "them. An alert is never a bare claim - it is a claim with its evidence attached, "
    "inspectable in one click. Relationships surfaced by analysis are stored with "
    "evidence status INFERRED and remain so until an investigator validates them.", BODY))

# ---------------------------------------------------------------- 6
A(Paragraph("6.  Constraints we imposed deliberately", H2))
A(Paragraph(
    "These are design decisions, not gaps. In a module concerning the safety of real "
    "people, restraint is a feature.", BODY))
A(kv_table([
    ["No emergency call is placed", "The SOS console is an in-platform dispatch workflow. "
     "Claiming otherwise could cost someone their life."],
    ["Location honesty", "Every position is labelled SIMULATED or DEVICE. An officer "
     "always knows whether a fix is real."],
    ["No person is labelled", "Detection output describes patterns requiring review. It "
     "never states that someone is a stalker or an offender."],
    ["Bands describe reporting", "Heatmap colour reflects recorded incident density, not "
     "danger, and the interface says so."],
    ["Human validation is mandatory", "Analytical findings stay INFERRED until an "
     "authorised officer confirms them."],
    ["Audit on every action", "Raising an SOS, changing its status and reviewing a pattern "
     "are each recorded with officer, timestamp and outcome."],
], widths=[44 * mm, PAGE_W - 2 * MARGIN - 44 * mm]))

# ---------------------------------------------------------------- 7
A(Paragraph("7.  Honest limitations", H2))
A(kv_table([
    ["Synthetic data", "All 426 incidents, both cases and every entity are fictional. The "
     "Delhi statistics cited in section 1 are real and stored separately as REFERENCE."],
    ["No live GPS", "Device location requires an authorised integration. The interface "
     "is built for it; the connection is not made."],
    ["No dispatch integration", "Connecting to real emergency services needs authorisation "
     "we do not have. The adapter interface exists and is documented."],
    ["Reporting bias", "Density reflects where complaints are filed, not where incidents "
     "occur. Under-reported areas will appear safer than they are - a limitation no "
     "algorithm can correct from complaint data alone."],
    ["Small routing graph", "11 waypoints over a demonstration area. Real deployment needs "
     "an actual road network."],
    ["Unvalidated thresholds", "Band thresholds and factor weights are reasoned but not yet "
     "calibrated against outcomes with serving officers."],
], widths=[40 * mm, PAGE_W - 2 * MARGIN - 40 * mm]))

# ---------------------------------------------------------------- 8
A(Paragraph("8.  Demonstration path", H2))
A(kv_table([
    ["1", "Sign in as <b>WSO-052</b> (Women Safety Officer) - a different role sees a "
     "different platform."],
    ["2", "Raise an SOS. Watch it auto-route to the nearest zone and pull emergency contacts."],
    ["3", "Move it RECEIVED → ASSIGNED → RESPONDING → RESOLVED, then try to skip "
     "a state - the server refuses."],
    ["4", "Open the heatmap. Change the incident-type filter and watch zones recolour from "
     "live data."],
    ["5", "Compute a safe route. Open a route's factor breakdown - lighting, alerts, "
     "service proximity."],
    ["6", "Open a repeated-encounter detection and inspect the actual events behind it."],
    ["7", "Click <b>Investigate Connection</b> on a pattern - it opens the network graph "
     "seeded with that subgraph."],
], widths=[10 * mm, PAGE_W - 2 * MARGIN - 10 * mm]))

A(Spacer(1, 4 * mm))
A(callout(
    "Closing position",
    "This module does not claim to prevent crime. It claims something narrower and "
    "defensible: that the warning signs are usually already in the system, recorded across "
    "separate complaints, and that connecting them is a solvable engineering problem. "
    "Every figure it shows can be traced to the records that produced it, and every "
    "conclusion waits for a human officer. We would rather build that honestly than build "
    "something that looks more capable than it is.", INDIGO))

A(Spacer(1, 5 * mm))
A(Paragraph(
    "<b>Live platform:</b> https://trinetra-rosy-gamma.vercel.app &nbsp;·&nbsp; "
    "<b>Sign in:</b> Service ID WSO-052<br/>"
    "All data synthetic. This module is investigative decision-support and does not "
    "determine guilt.", SMALL))

Doc(str(OUT)).build(story)
print(f"written: {OUT}")
print(f"size: {OUT.stat().st_size:,} bytes")
