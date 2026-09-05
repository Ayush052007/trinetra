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

OUT = Path(r"D:\Programming\claude\TriNetra\docs\TRINETRA_Mock_Murder_Case_Dossier.pdf")

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
                          "Standalone synthetic case for live ingestion demonstration")
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
    canvas.drawString(MARGIN, 9 * mm, "Mock homicide dossier · Not loaded into the platform")
    canvas.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(path, pagesize=A4,
                         leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN, bottomMargin=MARGIN,
                         title="TRINETRA - Mock Homicide Case File",
                         author="Team TRINETRA",
                         subject="Standalone synthetic homicide case for live demonstration")
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
MONO = S("mono", fontName="Courier", fontSize=8.2, leading=11.4,
         textColor=colors.HexColor("#26303F"))
MONO_W = S("monow", parent=MONO, fontName="Courier-Bold", textColor=colors.white)
DOCBOX = S("docbox", parent=BODY, fontSize=9.2, leading=14.6, alignment=TA_JUSTIFY)

story = []
A = story.append


def doc_header(ref, title, source_type, date):
    t = Table(
        [[Paragraph(f"<b>{title}</b>", CELL_W), Paragraph(f"<b>{ref}</b>", CELL_W)],
         [Paragraph(source_type, CELL), Paragraph(date, CELL)]],
        colWidths=[(PAGE_W - 2 * MARGIN) * 0.66, (PAGE_W - 2 * MARGIN) * 0.34],
        hAlign="LEFT",
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
    ]))
    return t


def narrative(text):
    t = Table([[Paragraph(text, DOCBOX)]], colWidths=[PAGE_W - 2 * MARGIN], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def data_table(header, rows, widths):
    data = [[Paragraph(h, MONO_W) for h in header]]
    data += [[Paragraph(str(c), MONO) for c in r] for r in rows]
    t = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, LINE),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------- COVER
A(Paragraph("Mock Homicide Case File", H1))
A(Paragraph(
    "A standalone synthetic case for live demonstration. Nothing here is loaded "
    "into TRINETRA in advance - these documents are meant to be pasted into the "
    "<b>AI &amp; NLP Analysis</b> page or uploaded through <b>Data Ingestion</b> "
    "during your presentation, so the audience watches the platform build the case "
    "from nothing in real time rather than seeing a pre-populated result.", BODY))
A(Spacer(1, 4 * mm))

A(kv_table([
    ["Case", "DEMO/HM-2026-0219 - Homicide Investigation, South Delhi"],
    ["Documents", "6 source records: FIR, post-mortem report, CDR extract, "
     "surveillance log, witness statement, financial dispute record"],
    ["Designed to show", "New-entity extraction, timeline reconstruction, alibi "
     "contradiction, motive-to-suspect linkage - none of which the existing seeded "
     "cases exercise"],
    ["Integration", "None. Not seeded, not committed to the database. Paste or "
     "upload live; nothing persists unless you choose to add it to the graph."],
], widths=[34 * mm, PAGE_W - 2 * MARGIN - 34 * mm]))

A(Spacer(1, 5 * mm))
A(callout(
    "Entirely fictional",
    "Every name, address, phone number, vehicle registration and financial detail "
    "below is invented for this demonstration. No real person, location, "
    "investigation or case is represented, and nothing here is derived from any "
    "real reported matter.", ROSE))

A(NextPageTemplate("Body"))
A(PageBreak())

# ---------------------------------------------------------------- SUGGESTED FLOW
A(Paragraph("Suggested live demonstration order", H2))
A(kv_table([
    ["1", "Paste Document 1 (FIR) into AI &amp; NLP Analysis. All entities appear "
     "as <b>new</b> - none pre-exist in the graph. This is the moment to say "
     "‘watch it build the case from nothing.’"],
    ["2", "Click Add to Knowledge Graph. Open Network Graph and show the suspect, "
     "victim and location nodes now connected."],
    ["3", "Paste Document 3 (CDR) and Document 5 (witness statement) next. The "
     "witness statement places the suspect at the scene; the CDR shows his phone "
     "was elsewhere at the same time. Point out the contradiction on screen."],
    ["4", "Paste Document 6 (financial dispute). A motive - a large, disputed "
     "payment - now connects to the same suspect the CDR and witness statement "
     "already named."],
    ["5", "Open Investigation Priority. The suspect should now rank highest - not "
     "because the system decided he did it, but because the most independent "
     "threads of evidence converge on him."],
    ["6", "Close on the disclaimer: every link is INFERRED until you validate it. "
     "Click Validate on one, and only one, to show the human decision step."],
], widths=[10 * mm, PAGE_W - 2 * MARGIN - 10 * mm]))

# ---------------------------------------------------------------- DOC 1
A(Paragraph("Document 1  -  First Information Report", H2))
A(Paragraph(
    "The primary unstructured record. Paste this first - it names the victim, the "
    "suspect, the location and the approximate time, and produces the widest "
    "initial spread of new entities.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("FIR2026-0219", "First Information Report",
             "South Delhi District Police", "Registered 19 February 2026"))
A(narrative(
    "Complaint received from the residence of <b>Vikram Oberoi</b>, aged 47, "
    "proprietor of a construction supply business, found deceased at his office "
    "premises at <b>Sector 18</b> on the morning of 19 February 2026. Body "
    "discovered by office staff at approximately 0915 hours. Initial assessment "
    "indicates death occurred the previous evening.<br/><br/>"
    "Deceased is survived by his business partner <b>Sanjay Khurana</b>, with whom "
    "he had an ongoing commercial dispute, and a former site supervisor "
    "<b>Deepak Bhalla</b>, terminated from employment six weeks prior following "
    "an internal audit. Security personnel report that a visitor matching "
    "Deepak Bhalla's description was seen entering the premises at approximately "
    "1940 hours on 18 February 2026. Deepak Bhalla called ahead using phone "
    "number <b>9871122334</b> to request entry.<br/><br/>"
    "Sanjay Khurana states he was at a client dinner in <b>Gurugram</b> that "
    "evening and did not visit the office. Case registered under relevant "
    "sections. Forensic and call-record examination directed."))

A(Spacer(1, 3 * mm))
A(callout(
    "Measured extraction result",
    "Run against the platform: <b>10 entities at 0.785 mean confidence, 9 of them "
    "genuinely new</b> - Vikram Oberoi, Sanjay Khurana, Deepak Bhalla, Sector 18 "
    "and the phone number all created fresh, none colliding with the background "
    "population. Only Gurugram resolves to an existing location (l4), which is "
    "correct - it is a real place named in the seeded case too. Two relationships "
    "extract correctly and attach to the right person: <i>Deepak Bhalla CALLED "
    "9871122334</i> and <i>Deepak Bhalla OWNED 9871122334</i>.<br/><br/>"
    "These names were deliberately checked against the platform's own "
    "corpus-generator name pools before writing this document - with roughly "
    "3,000 generated background entities, an unchecked common name would collide "
    "with an existing record almost by default. Worth remembering if you write "
    "your own test documents.", GREEN))

# ---------------------------------------------------------------- DOC 2
A(Paragraph("Document 2  -  Post-Mortem Examination Report", H2))
A(Paragraph(
    "Establishes the time window the rest of the case must be checked against. "
    "Not designed for NLP extraction - this is reference material to read aloud "
    "when explaining the timeline.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("PM-0219-A", "Post-Mortem Examination Report",
             "Forensic Medicine Department", "Examined 19 February 2026"))
A(narrative(
    "Deceased identified as Vikram Oberoi, male, 47 years. Cause of death: "
    "blunt force trauma to the occipital region, consistent with a single "
    "forceful impact. No defensive wounds noted.<br/><br/>"
    "Based on rigor mortis, lividity and gastric contents, time of death is "
    "estimated between <b>1900 and 2100 hours on 18 February 2026</b>. No "
    "evidence of forced entry at the premises. Deceased's own office key was "
    "found on his person, suggesting the visitor was known to him and admitted "
    "voluntarily."))

# ---------------------------------------------------------------- DOC 3
A(Paragraph("Document 3  -  Call Detail Record Extract", H2))
A(Paragraph(
    "The contradiction document. Deepak Bhalla's phone places him near the "
    "scene at the estimated time of death - directly testing the timeline "
    "against the post-mortem window above.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("CDR-9871122334", "Call Detail Record Extract",
             "Authorised telecom request", "Period: 18 February 2026, 1800-2200"))
A(Spacer(1, 1.5 * mm))
A(data_table(
    ["TIME", "A-PARTY", "B-PARTY", "DUR", "CELL ID", "TYPE"],
    [
        ["18:52", "9871122334", "9944556677", "38", "SDL-18-C2", "OUT"],
        ["19:41", "9871122334", "9812309988", "12", "SDL-18-C2", "OUT"],
        ["20:15", "9871122334", "-", "-", "SDL-18-C1", "SMS"],
        ["20:47", "9871122334", "9944556677", "94", "SDL-18-C1", "OUT"],
        ["21:33", "9871122334", "8800112233", "205", "SDL-EXT-D3", "OUT"],
    ],
    widths=[16 * mm, 30 * mm, 30 * mm, 14 * mm, 26 * mm, 15 * mm]))
A(Spacer(1, 2 * mm))
A(Paragraph(
    "Cell tower <b>SDL-18-C1/C2</b> covers Sector 18, South Extension - the "
    "location of the office. The device sits on that tower from 1852 to 2047 "
    "hours, inside the post-mortem window, before moving to a different tower "
    "at 2133. This is the entity resolution challenge: the phone number here "
    "must be recognised as the same 9871122334 named in the FIR as Deepak "
    "Bhatia's, not treated as an unrelated new record.", SMALL))

# ---------------------------------------------------------------- DOC 4
A(Paragraph("Document 4  -  Security Gate Log", H2))
A(Paragraph(
    "Structured entry/exit record corroborating the CDR placement.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("SGL-0219", "Security Gate Log Extract",
             "Premises security register", "18 February 2026"))
A(Spacer(1, 1.5 * mm))
A(data_table(
    ["TIME", "VISITOR / VEHICLE", "PURPOSE STATED", "EXIT TIME"],
    [
        ["18:30", "Vikram Oberoi (resident)", "-", "-"],
        ["19:38", "Visitor, DL 5S BR 7743", "Meeting - D. Bhatia", "not logged"],
        ["21:02", "Office staff, on foot", "Delivery drop", "21:10"],
        ["09:15", "Office staff (19-Feb)", "Opening premises", "-"],
    ],
    widths=[18 * mm, 48 * mm, 45 * mm, 25 * mm]))
A(Spacer(1, 2 * mm))
A(Paragraph(
    "The visitor entry at 1938 has no logged exit time - unusual against the "
    "otherwise consistent gate register, and consistent with the office being "
    "found undisturbed the next morning rather than secured on departure.", SMALL))

# ---------------------------------------------------------------- DOC 5
A(Paragraph("Document 5  -  Witness Statement", H2))
A(Paragraph(
    "A neighbouring shopkeeper's account. Written with the hedging real "
    "witnesses use - useful for testing extraction against uncertain, "
    "conversational input rather than a clean official record.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("WS-0219-02", "Statement of Witness",
             "Recorded statement", "Recorded 20 February 2026"))
A(narrative(
    "My shop is two doors from the construction supply office. I was closing up "
    "that evening, must have been close to eight, when I saw a car pull up - "
    "silver, maybe grey, I am not certain of the make. A man got out and went "
    "inside. I have seen him before, he used to work there I believe, before he "
    "left the company.<br/><br/>"
    "I did not see him leave. I went home shortly after and did not think "
    "anything of it until the police came round asking questions the next "
    "morning. I could not tell you the exact number plate, but it looked like a "
    "Delhi registration.<br/><br/>"
    "I am willing to look at photographs if it would help."))

A(Spacer(1, 3 * mm))
A(callout(
    "Why this document matters for the demo",
    "The witness gives a location, an approximate time and a hedged "
    "identification - ‘I have seen him before, I believe’ - without a name "
    "or a full vehicle registration. This is realistic testimony, and it should "
    "corroborate rather than independently prove anything. Point out that the "
    "platform treats this the same way as the FIR partial-plate statement in "
    "the earlier dossier: extracted, flagged as uncorroborated, never promoted "
    "to fact on its own.", ACCENT))

# ---------------------------------------------------------------- DOC 6
A(Paragraph("Document 6  -  Financial Dispute Record", H2))
A(Paragraph(
    "Establishes motive. This is the document to paste last, so the audience "
    "watches the priority ranking shift once a financial thread joins the "
    "physical and testimonial ones already entered.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("FD-0219", "Internal Audit Note - Financial Dispute",
             "Company records, produced under request", "Dated 4 January 2026"))
A(narrative(
    "Internal audit dated 4 January 2026 identifies discrepancies of "
    "approximately <b>Rs 18,40,000</b> in site-material procurement records "
    "signed off by then-supervisor <b>Deepak Bhalla</b> over the preceding "
    "eight months. Vikram Oberoi terminated Bhatia's employment on 6 January "
    "2026 and initiated recovery proceedings through the company's legal "
    "counsel.<br/><br/>"
    "Correspondence on file shows Bhatia disputed the findings in writing on "
    "three occasions between January and February 2026, the most recent dated "
    "12 February 2026, six days before the date of the incident, describing the "
    "recovery claim as ‘unjust and ruinous’ to his standing in the "
    "industry."))

# ---------------------------------------------------------------- SUMMARY
A(Paragraph("What the platform should converge on", H2))
A(Paragraph(
    "Not a verdict - a triage signal, with its reasoning visible. Four "
    "independent threads name the same person:", BODY))
A(kv_table([
    ["Opportunity", "Gate log places a visitor matching his description at the "
     "premises at 19:38, no exit logged"],
    ["Physical placement", "CDR places his phone on the premises cell tower "
     "through the post-mortem time window"],
    ["Testimony", "A witness recalls a former employee entering around the "
     "same time, hedged and uncorroborated on its own"],
    ["Motive", "A disputed recovery claim of Rs 18,40,000, escalating in "
     "writing six days before the incident"],
], widths=[34 * mm, PAGE_W - 2 * MARGIN - 34 * mm]))

A(Spacer(1, 4 * mm))
A(callout(
    "Say this out loud during the demo",
    "‘No single document proves anything. The gate log alone is an "
    "unlogged exit. The CDR alone is a phone on a tower. The witness alone is "
    "a hedged memory. The financial record alone is a dispute that happens "
    "constantly in business. TRINETRA does not decide guilt from any one of "
    "these - it shows an investigator that four independent threads converge "
    "on the same person, with the evidence behind each one visible and "
    "traceable. That convergence is the lead. The decision stays with the "
    "officer.’", INDIGO))

A(Spacer(1, 5 * mm))
A(Paragraph(
    "This dossier is not committed to the platform database or the project "
    "repository. Paste or upload the documents live; nothing persists unless "
    "you choose to add it to the knowledge graph during the demonstration.",
    SMALL))

Doc(str(OUT)).build(story)
print(f"written: {OUT}")
print(f"size: {OUT.stat().st_size:,} bytes")
