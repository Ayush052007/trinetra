"""Pattern definitions for entity recognition in Indian investigative text.

These are deterministic, inspectable rules - not a statistical model. Every
match carries the exact character span that produced it, which is what lets
the UI highlight the source text behind each extracted entity.

Scope is stated honestly: this recognises well-formed structured identifiers
and gazetteer-known names. It is not a trained NER model and does not claim
model-level recall on free prose. The NlpEngine protocol in engine.py exists
so a transformer or spaCy pipeline can be substituted where one is available.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------- structured

# Indian mobile numbers: optional +91/0 prefix, then a 10-digit number
# beginning 6-9. Also accepts the masked form used in the demo corpus
# (+91-98xxxx1123), because case files routinely carry redacted numbers.
PHONE = re.compile(
    r"(?<![\d])(?:\+?91[\-\s]?|0)?"
    r"(?:[6-9]\d{9}|[6-9]\d{1,3}[xX]{2,6}\d{2,4})"
    r"(?![\d])"
)

# Indian vehicle registration: SS-NN-LL-NNNN with flexible separators, plus
# the masked demo form DL-0X-XX-4471.
VEHICLE = re.compile(
    r"\b[A-Z]{2}[\s\-]?\d{1,2}[A-Z]?[\s\-]?[A-Z]{1,3}[\s\-]?\d{3,4}\b"
    r"|\b[A-Z]{2}[\s\-]\d[A-Z][\s\-][A-Z]{2}[\s\-]\d{4}\b"
)

# Currency: symbol or word form, with Indian digit grouping and lakh/crore.
CURRENCY = re.compile(
    r"(?:₹|Rs\.?|INR)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:lakh|lakhs|crore|crores|k))?"
    r"|\b\d[\d,]*(?:\.\d+)?\s?(?:lakh|lakhs|crore|crores)\b",
    re.IGNORECASE,
)

# Case / FIR identifiers, including the project's own formats
# (FIR2026-0147, NX-2026-0147, DEMO/WS-2026-0417).
CASE_ID = re.compile(
    r"\b(?:FIR|CASE|NX|WS|CR)[\s/\-]?\d{2,4}[\s/\-]?\d{2,4}\b"
    r"|\b[A-Z]{2,6}/[A-Z]{2}-\d{4}-\d{3,4}\b",
    re.IGNORECASE,
)

SOCIAL_HANDLE = re.compile(r"(?<![\w])@[A-Za-z][A-Za-z0-9._]{2,29}\b")

EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

IMEI = re.compile(r"\b(?:IMEI[\s:]*)?\d{15}\b", re.IGNORECASE)

# Dates: 10 January / 10 Jan 2026 / 10-01-2026 / 2026-01-10, and the relative
# "Day N" labels the Women Safety demo case uses throughout.
_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
DATE = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})(?:\s+\d{{4}})?\b"
    rf"|\b(?:{_MONTHS})\s+\d{{1,2}}(?:,\s*\d{{4}})?\b"
    r"|\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
DAY_LABEL = re.compile(r"\bDay\s+\d{1,3}\b", re.IGNORECASE)

TIME_OF_DAY = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\s?(?:hrs|am|pm)?\b", re.IGNORECASE)

# ---------------------------------------------------------------- person names

# Honorifics that reliably precede a personal name in Indian case text.
HONORIFIC = r"(?:Mr|Mrs|Ms|Dr|Shri|Smt|Sh|Kum|Prof|Insp|SI|ASI|HC|Const)\.?"

# "Mr Rahul Sharma", "Smt. A. Sharma"
HONORIFIC_NAME = re.compile(rf"\b{HONORIFIC}\s+([A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){{0,3}})")

# Initial-form names common in redacted case files: "R. Verma", "A. Sharma".
INITIAL_NAME = re.compile(r"\b[A-Z]\.\s?[A-Z][a-z]{2,}\b")

# Two-to-three capitalised tokens in sequence: "Rahul Sharma".
CAPITALISED_NAME = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2}\b")

# Tokens that look like names but are sentence-initial function words or
# organisational vocabulary. Filtering these is what keeps precision usable.
NAME_STOPWORDS = {
    "The", "This", "That", "These", "Those", "There", "Then", "They", "Their",
    "It", "Its", "As", "At", "On", "In", "By", "For", "From", "With", "Was",
    "Were", "Has", "Have", "Had", "Been", "Being", "And", "But", "Not", "All",
    "Any", "Case", "Report", "Police", "Station", "Sector", "Phone", "Number",
    "Vehicle", "Account", "Bank", "Transaction", "Records", "Record", "Date",
    "Day", "Time", "Location", "Address", "Suspect", "Victim", "Witness",
    "Accused", "Complainant", "Officer", "Investigation", "Statement", "Note",
    "Subject", "Further", "During", "After", "Before", "While", "When", "Where",
    "According", "Following", "Based", "Both", "Between", "Same", "Also",
    "However", "Additionally", "Subsequently", "Later", "Meanwhile",
}

# Organisation suffixes seen in the project corpus.
ORG_SUFFIX = re.compile(
    r"\b[A-Z][A-Za-z&.\-]*(?:\s+[A-Z][A-Za-z&.\-]*){0,4}\s+"
    r"(?:Pvt\.?\s?Ltd\.?|Private\s+Limited|Ltd\.?|LLP|Limited|Co\.?|Company|"
    r"Corporation|Enterprises|Traders|Trading|Logistics|Finserv|Industries|"
    r"Services|Solutions|Agencies|Associates|Bank)\b"
)

# ------------------------------------------------------------ relation triggers

# Each trigger maps surface verbs to a relationship type in the project's
# controlled vocabulary. `directed` marks whether subject->object ordering is
# meaningful (money moves one way; a meeting does not).
RELATION_TRIGGERS: list[dict] = [
    {
        "type": "CALLED",
        "label": "Called",
        "directed": True,
        "patterns": [
            r"\bcalled\b", r"\bcontacted\b", r"\bphoned\b", r"\brang\b",
            r"\bspoke (?:to|with)\b", r"\bcommunicated with\b",
            r"\bmade (?:a )?calls? to\b",
        ],
    },
    {
        "type": "MET",
        "label": "Met",
        "directed": False,
        "patterns": [r"\bmet\b", r"\bmeeting with\b", r"\bmet with\b", r"\brendezvous(?:ed)? with\b"],
    },
    {
        "type": "VISITED",
        "label": "Visited",
        "directed": True,
        "patterns": [r"\bvisited\b", r"\bwent to\b", r"\btravelled to\b", r"\btraveled to\b", r"\bpresent at\b"],
    },
    {
        "type": "TRANSFERRED_MONEY",
        "label": "Transferred Money",
        "directed": True,
        "patterns": [
            r"\btransferred\b", r"\bremitted\b", r"\bpaid\b", r"\bsent (?:₹|Rs|money)\b",
            r"\bdeposited\b", r"\bcredited\b", r"\bwired\b",
        ],
    },
    {
        "type": "OWNED",
        "label": "Owned",
        "directed": True,
        "patterns": [
            r"\bowns\b", r"\bowned\b", r"\bregistered (?:owner|to|in the name of)\b",
            r"\bbelongs to\b", r"\bin possession of\b", r"\busing (?:phone|number|vehicle)\b",
        ],
    },
    {
        "type": "WORKED_FOR",
        "label": "Worked For",
        "directed": True,
        "patterns": [r"\bworks? (?:for|at|with)\b", r"\bworked (?:for|at|with)\b", r"\bemployed (?:by|at)\b", r"\bemployee of\b"],
    },
    {
        "type": "ASSOCIATED_WITH",
        "label": "Associated With",
        "directed": False,
        "patterns": [r"\bassociated with\b", r"\blinked (?:to|with)\b", r"\bconnected (?:to|with)\b", r"\baffiliated with\b"],
    },
    {
        "type": "sighted_at",
        "label": "Sighted At",
        "directed": True,
        "patterns": [r"\bsighted (?:at|near)\b", r"\bspotted (?:at|near)\b", r"\bseen (?:at|near|outside)\b", r"\bobserved (?:at|near)\b"],
    },
    {
        "type": "resides_at",
        "label": "Resides At",
        "directed": True,
        "patterns": [r"\bresides? at\b", r"\bliving at\b", r"\blives at\b", r"\bresident of\b"],
    },
    {
        "type": "commutes_to",
        "label": "Commutes To",
        "directed": True,
        "patterns": [r"\bcommutes? (?:to|between)\b", r"\btravels? to work\b"],
    },
    {
        "type": "sent_messages_to",
        "label": "Sent Messages To",
        "directed": True,
        "patterns": [r"\bsent (?:messages?|texts?|sms)\b", r"\bmessaged\b", r"\bmessages? to\b"],
    },
    {
        "type": "complaint_filed_against",
        "label": "Complaint Filed Against",
        "directed": True,
        "patterns": [r"\bfiled a complaint against\b", r"\bcomplained against\b", r"\blodged (?:an? )?(?:FIR|complaint) against\b"],
    },
    {
        "type": "followed",
        "label": "Followed",
        "directed": True,
        "patterns": [r"\bfollowed\b", r"\btrailed\b", r"\bpursued\b", r"\bbeing followed by\b"],
    },
    {
        "type": "witnessed",
        "label": "Witnessed",
        "directed": True,
        "patterns": [r"\bwitnessed\b", r"\bsaw the\b", r"\bobserved the incident\b"],
    },
]

# Compiled once at import.
for _trigger in RELATION_TRIGGERS:
    _trigger["regex"] = re.compile("|".join(_trigger["patterns"]), re.IGNORECASE)


SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
