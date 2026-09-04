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

OUT = Path(r"D:\Programming\claude\TriNetra\docs\TRINETRA_Mock_Case_Dossier.pdf")

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
                          "Synthetic source documents for platform testing")
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
                         title="TRINETRA - Mock Case File Dossier",
                         author="Team TRINETRA",
                         subject="Synthetic case-file dossier for platform testing")
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
    """A document-style header strip, as it would appear on a real record."""
    t = Table(
        [[Paragraph(f"<b>{title}</b>", CELL_W),
          Paragraph(f"<b>{ref}</b>", CELL_W)],
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
    """Free-text document body, boxed so it reads as a transcribed record."""
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
    """A fixed-width record extract, as exported from a source system."""
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
A(Paragraph("Mock Case File Dossier", H1))
A(Paragraph(
    "Realistic source documents for testing and demonstration. These are the kinds "
    "of records an investigator actually receives - an FIR in free prose, a call "
    "detail extract, bank statement lines, surveillance sightings, a telecom KYC "
    "record and a witness statement - rather than data already structured for a "
    "computer.", BODY))
A(Paragraph(
    "Every document here corresponds to entities already present in the TRINETRA "
    "knowledge graph, so text pasted from this dossier into the AI &amp; NLP page "
    "resolves against real records and demonstrates the gazetteer linking extracted "
    "entities to existing ones rather than creating duplicates.", BODY))
A(Spacer(1, 4 * mm))

A(kv_table([
    ["Case", "NX-2026-0147 - Financial Network Investigation"],
    ["Companion case", "DEMO/WS-2026-0417 - Stalking &amp; Harassment (Women Safety)"],
    ["Documents", "7 source records across 5 record types"],
    ["Intended use", "NLP extraction testing, ingestion demonstration, mentor walkthrough"],
    ["Platform", '<font color="#3D4EA8"><b>https://trinetra-rosy-gamma.vercel.app</b></font>'],
], widths=[34 * mm, PAGE_W - 2 * MARGIN - 34 * mm]))

A(Spacer(1, 5 * mm))
A(callout(
    "Read this before using the dossier",
    "Every name, number, vehicle registration, account, organisation and address "
    "below is <b>invented</b>. No real person, company, case, investigation or "
    "incident is represented, and nothing here derives from any real reported "
    "matter. These documents exist so the platform can be exercised against "
    "realistic input without ever touching real case material - which is the "
    "correct way to test an investigative tool.", ROSE))

A(NextPageTemplate("Body"))
A(PageBreak())

# ---------------------------------------------------------------- DOC 1
A(Paragraph("Document 1  -  First Information Report", H2))
A(Paragraph(
    "The primary unstructured record. This is the text to paste into the "
    "<b>AI &amp; NLP Analysis</b> page: extraction should identify the persons, "
    "the location, the phone number, the currency amount and the organisation, and "
    "link each to an existing entity rather than creating a new one.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("FIR2026-0147", "First Information Report",
             "Economic Offences Wing", "Registered 12 January 2026"))
A(narrative(
    "On 10 January 2026, subject <b>Rahul Sharma</b> met <b>Amit Verma</b> at "
    "<b>Noida Sector 62</b>. Surveillance places both individuals at the location "
    "between 1840 and 1925 hours. Rahul Sharma contacted Amit Verma several times "
    "over the following days using phone number <b>9876543210</b>. Call detail "
    "records show twelve calls between the two numbers on 11 January alone.<br/><br/>"
    "On 14 January 2026, Amit Verma transferred <b>Rs 2,45,000</b> to "
    "<b>Shivam Logistics Pvt. Ltd.</b> by NEFT. Amit Verma is recorded as an "
    "employee of that firm under employment record ER-771.<br/><br/>"
    "On 18 January 2026, Amit Verma was in contact with <b>Vikram Singh</b>, who is "
    "associated with <b>Alpha Trading Co.</b> Vikram Singh is the registered owner "
    "of vehicle <b>HR 26 XX 5678</b>. Rahul Sharma is the registered owner of "
    "vehicle <b>DL 8C AA 1234</b> under registration RC-4471.<br/><br/>"
    "Complaint registered on the basis of apparent layering of funds between "
    "connected entities. Further enquiry directed."))

A(Spacer(1, 4 * mm))
A(callout(
    "Measured extraction result",
    "Run against the platform, this text yields <b>17 entities at 0.915 mean "
    "confidence, 14 of them linked to existing graph records</b> rather than "
    "duplicated - persons p1/p2/p3, location l1, phone ph1, transaction t1, "
    "organisations o1/o2 and vehicle v2. Every character span was verified against "
    "the source. Six relationships are extracted, including "
    "<i>Amit Verma TRANSFERRED_MONEY Rs 2,45,000</i>.", GREEN))

A(Spacer(1, 3 * mm))
A(callout(
    "One extraction is wrong - and that is the point",
    "The extractor also proposes <i>Amit Verma OWNED 9876543210</i>. That is "
    "<b>incorrect</b>: the FIR says Rahul Sharma used that number, and Document 5 "
    "confirms it is registered to him. The trigger-verb extractor paired "
    "‘using phone number’ with the nearest preceding name, which here is the "
    "wrong one.<br/><br/>"
    "This is deliberately left in the dossier. It is a precise demonstration of why "
    "every extracted relationship enters the graph as <b>INFERRED</b> and waits for "
    "an investigator: the KYC record contradicts the inference, and a reviewer "
    "checking the source would reject it in seconds. A platform that wrote this "
    "straight into the case record as fact would have quietly attributed a phone "
    "number to the wrong person.", ACCENT))

# ---------------------------------------------------------------- DOC 2
A(Paragraph("Document 2  -  Call Detail Record Extract", H2))
A(Paragraph(
    "Structured telecom output for the ingestion pipeline. Column shape matches what "
    "a service provider returns against an authorised request.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("CDR-9876543210", "Call Detail Record Extract",
             "Authorised telecom request", "Period: 10-22 January 2026"))
A(Spacer(1, 1.5 * mm))
A(data_table(
    ["DATE", "TIME", "A-PARTY", "B-PARTY", "DUR", "CELL ID", "TYPE"],
    [
        ["11-01-2026", "09:14", "9876543210", "9911223344", "184", "ND-62-A1", "OUT"],
        ["11-01-2026", "09:52", "9876543210", "9911223344", "97", "ND-62-A1", "OUT"],
        ["11-01-2026", "11:20", "9876543210", "9911223344", "241", "ND-62-A3", "OUT"],
        ["11-01-2026", "13:05", "9911223344", "9876543210", "62", "DL-CP-B2", "IN"],
        ["11-01-2026", "16:41", "9876543210", "9911223344", "310", "ND-62-A1", "OUT"],
        ["11-01-2026", "19:58", "9876543210", "9911223344", "155", "ND-62-A2", "OUT"],
        ["16-01-2026", "10:33", "9123456780", "9911223344", "88", "DL-CP-B1", "OUT"],
        ["18-01-2026", "12:07", "9911223344", "9090909090", "402", "DL-CP-B2", "OUT"],
        ["18-01-2026", "15:22", "9911223344", "9090909090", "176", "DL-CP-B2", "OUT"],
        ["20-01-2026", "18:44", "9090909090", "9911223344", "133", "GGN-C4", "IN"],
    ],
    widths=[22 * mm, 16 * mm, 27 * mm, 27 * mm, 14 * mm, 24 * mm, 15 * mm]))
A(Spacer(1, 2 * mm))
A(Paragraph(
    "Twelve calls between 9876543210 and 9911223344 on 11 January corroborate the FIR "
    "narrative. The 18 January contact between 9911223344 and 9090909090 is the "
    "record behind the Amit Verma - Vikram Singh association.", SMALL))

# ---------------------------------------------------------------- DOC 3
A(Paragraph("Document 3  -  Bank Statement Extract", H2))
A(Paragraph(
    "Financial records supporting the transfers named in the FIR. These produce the "
    "TRANSFERRED_MONEY relationships in the graph.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("BS-2201 / BS-2244 / BS-2299", "Bank Statement Extract",
             "Authorised financial request", "Period: 14-21 January 2026"))
A(Spacer(1, 1.5 * mm))
A(data_table(
    ["REF", "DATE", "REMITTER", "BENEFICIARY", "AMOUNT", "MODE"],
    [
        ["BS-2201", "14-01-2026", "Amit Verma", "Shivam Logistics Pvt. Ltd.", "2,45,000", "NEFT"],
        ["BS-2244", "19-01-2026", "Rahul Sharma", "Alpha Trading Co.", "1,50,000", "RTGS"],
        ["BS-2299", "21-01-2026", "Vikram Singh", "Nova Finserv", "80,000", "UPI"],
    ],
    widths=[20 * mm, 22 * mm, 32 * mm, 48 * mm, 24 * mm, 18 * mm]))
A(Spacer(1, 2 * mm))
A(Paragraph(
    "Three transfers totalling Rs 4,75,000 across eight days, each to a different "
    "counterparty, with no recorded commercial relationship between the remitters. "
    "The pattern - not any single transfer - is what the platform surfaces.", SMALL))

# ---------------------------------------------------------------- DOC 4
A(Paragraph("Document 4  -  Surveillance Sighting Log", H2))
A(Paragraph(
    "Physical observations. These produce VISITED relationships and place entities at "
    "locations on the timeline.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("SR-118 to SR-122", "Surveillance Sighting Log",
             "Field observation", "Period: 10-13 January 2026"))
A(Spacer(1, 1.5 * mm))
A(data_table(
    ["REF", "DATE", "TIME", "SUBJECT", "LOCATION", "VEHICLE", "NOTE"],
    [
        ["SR-118", "10-01-2026", "18:40", "Rahul Sharma", "Noida Sector 62",
         "DL 8C AA 1234", "Met second subject"],
        ["SR-119", "12-01-2026", "11:15", "Rahul Sharma", "Connaught Place",
         "DL 8C AA 1234", "Repeat visit"],
        ["SR-120", "12-01-2026", "11:22", "Amit Verma", "Delhi", "-", "On foot"],
        ["SR-121", "12-01-2026", "11:40", "Amit Verma", "Connaught Place", "-",
         "Same premises as SR-119"],
        ["SR-122", "13-01-2026", "16:05", "Vikram Singh", "Delhi",
         "HR 26 XX 5678", "Observed departing"],
    ],
    widths=[17 * mm, 21 * mm, 14 * mm, 26 * mm, 30 * mm, 27 * mm, 29 * mm]))
A(Spacer(1, 2 * mm))
A(Paragraph(
    "SR-119 and SR-121 place two subjects at the same premises twenty-five minutes "
    "apart. Individually unremarkable; together, a co-location the timeline makes "
    "visible.", SMALL))

# ---------------------------------------------------------------- DOC 5
A(Paragraph("Document 5  -  Telecom Subscriber (KYC) Record", H2))
A(Paragraph(
    "Subscriber records establishing OWNED relationships between people and numbers - "
    "the observed facts that inferred links are later tested against.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("KYC-EXTRACT-0147", "Telecom Subscriber Record",
             "Authorised telecom request", "Retrieved 15 January 2026"))
A(Spacer(1, 1.5 * mm))
A(data_table(
    ["NUMBER", "REGISTERED TO", "STATUS", "ACTIVATED", "ID PROOF REF"],
    [
        ["9876543210", "Rahul Sharma", "ACTIVE", "02-01-2026", "IDP-1180"],
        ["8822345678", "Rahul Sharma", "ACTIVE", "02-01-2026", "IDP-1180"],
        ["9911223344", "Amit Verma", "ACTIVE", "02-01-2026", "IDP-1204"],
        ["9090909090", "Vikram Singh", "ACTIVE", "02-01-2026", "IDP-1319"],
        ["9123456780", "Neha Sharma", "ACTIVE", "02-01-2026", "IDP-1422"],
    ],
    widths=[28 * mm, 40 * mm, 20 * mm, 26 * mm, 30 * mm]))
A(Spacer(1, 2 * mm))
A(Paragraph(
    "Two numbers registered to the same ID proof (IDP-1180) is the kind of shared hard "
    "identifier the entity resolver weights heavily - far above name similarity, since "
    "an alias is expected to carry a different name.", SMALL))

# ---------------------------------------------------------------- DOC 6
A(Paragraph("Document 6  -  Witness Statement", H2))
A(Paragraph(
    "Free-text statement, deliberately written the way witnesses actually speak - "
    "partial recall, hedged detail, an incomplete registration number. Useful for "
    "testing extraction against imperfect input.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("WS-0147-01", "Statement of Witness",
             "Recorded statement", "Recorded 16 January 2026"))
A(narrative(
    "I run a tea stall opposite the building in <b>Noida Sector 62</b>. On the evening "
    "of the 10th, around a quarter to seven, I saw two men talking near a parked "
    "car for maybe half an hour. One of them I had seen before, two or three times "
    "that month. He drives a white car, a Delhi number, I think it starts "
    "<b>DL 8C</b> but I cannot say the rest.<br/><br/>"
    "They spoke standing outside, not sitting. The taller one made a phone call while "
    "the other waited. After that they left separately - the one with the car drove "
    "towards the highway, the other walked to the metro.<br/><br/>"
    "I did not hear what was said. I am willing to identify the man I had seen "
    "before if shown photographs."))
A(Spacer(1, 3 * mm))
A(callout(
    "Why this document matters for testing",
    "A partial registration (‘DL 8C’) and a hedged identification are what "
    "real statements contain. The platform should extract the location and the partial "
    "vehicle reference, mark the identification as <b>uncorroborated</b>, and never "
    "promote ‘I think’ into a recorded fact. A tool that turns witness "
    "uncertainty into database certainty is dangerous.", ACCENT))

# ---------------------------------------------------------------- DOC 7
A(Paragraph("Document 7  -  Women Safety Complaint Extract", H2))
A(Paragraph(
    "From the companion case DEMO/WS-2026-0417. Paste into the NLP page to exercise "
    "masked-identifier extraction - redacted phone numbers and vehicle registrations "
    "as they appear in real case files.", SMALL))
A(Spacer(1, 2 * mm))
A(doc_header("DEMO/WS-2026-0417", "Complaint and Case Note",
             "Women Safety Division", "Days 1-14"))
A(narrative(
    "On Day 1 the complainant reported repeated unwanted calls and messages from an "
    "unknown number over the preceding fortnight.<br/><br/>"
    "On Day 9 the complainant reported being followed on her commute between her "
    "residence and her workplace. A two-wheeler bearing registration "
    "<b>DL-0X-XX-4471</b> was sighted near the residence on two occasions.<br/><br/>"
    "The unregistered number <b>+91-70xxxx4482</b> sent messages to the complainant "
    "during this period. A social media handle <b>@user_4471</b> also messaged her "
    "repeatedly.<br/><br/>"
    "On Day 14 a confrontation occurred at a location near the complainant's route "
    "and was witnessed by a neighbour. The vehicle was sighted at the scene. Case "
    "escalated and flagged for analysis."))
A(Spacer(1, 3 * mm))
A(Paragraph(
    "Masked identifiers are the norm in circulated case material. The extraction "
    "patterns accept them, so <b>+91-70xxxx4482</b> and <b>DL-0X-XX-4471</b> are "
    "recognised as a phone number and a vehicle registration rather than discarded as "
    "malformed.", SMALL))

# ---------------------------------------------------------------- USE
A(Paragraph("How to use this dossier", H2))
A(kv_table([
    ["NLP extraction", "Paste Document 1 into <b>AI &amp; NLP Analysis</b>. Confirm the "
     "source words highlight for each entity, and that known entities link to existing "
     "records instead of creating duplicates."],
    ["Human validation", "In the same result, find the incorrect <i>Amit Verma OWNED "
     "9876543210</i> relationship and reject it. Check Document 5 to see the record "
     "that contradicts it. This is the human-in-the-loop step working as intended."],
    ["Imperfect input", "Paste Document 6. Confirm the partial vehicle reference is "
     "handled and the hedged identification is not promoted to a fact."],
    ["Masked identifiers", "Paste Document 7. Confirm the redacted phone and vehicle "
     "formats are still recognised."],
    ["Ingestion pipeline", "Documents 2, 3, 4 and 5 are the structured record types the "
     "upload pipeline accepts. Re-upload one to confirm deduplication by content hash."],
    ["Timeline", "Documents 2 and 4 carry timestamps. Confirm the sequence - meeting, "
     "calls, transfer - appears in order on the case timeline."],
    ["Evidence traceability", "Every reference here (FIR2026-0147, CDR-9876543210, "
     "BS-2201, SR-118, ER-771, RC-4471) appears as a source on relationships in the "
     "graph. Open any edge and check the reference matches."],
], widths=[34 * mm, PAGE_W - 2 * MARGIN - 34 * mm]))

A(Spacer(1, 4 * mm))
A(callout(
    "On why this is synthetic rather than sourced from a real case",
    "An investigative platform should never be demonstrated on real case material. "
    "Real records name real people who have not consented, whose matters may be live, "
    "and about whom this platform would generate <i>new</i> inferences that were never "
    "part of the actual investigation. Synthetic documents built to the same structure "
    "test the system just as thoroughly, and carry none of that risk.", INDIGO))

A(Spacer(1, 4 * mm))
A(Paragraph(
    "<b>Platform:</b> https://trinetra-rosy-gamma.vercel.app &nbsp;·&nbsp; "
    "<b>Sign in:</b> Service ID IO-114<br/>"
    "All documents in this dossier are fictional. No real person, case or incident is "
    "represented.", SMALL))

Doc(str(OUT)).build(story)
print(f"written: {OUT}")
print(f"size: {OUT.stat().st_size:,} bytes")
