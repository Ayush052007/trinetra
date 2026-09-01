"""Entity and relationship extraction from unstructured investigative text.

Pipeline:

    text -> sentence split -> structured NER (regex)
         -> gazetteer match (known entities + aliases)
         -> heuristic person/organisation detection
         -> normalisation -> deduplication (longest span wins)
         -> relationship extraction (trigger verbs over ordered spans)
         -> confidence scoring

Everything is deterministic and span-anchored. A caller can always ask "which
characters produced this?" and get an exact answer, which is what makes the
extraction reviewable rather than merely plausible.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from trinetra_nlp import patterns as P


@dataclass
class ExtractedEntity:
    """One recognised entity, anchored to its source characters."""

    text: str
    type: str
    normalized: str
    start: int
    end: int
    confidence: float
    method: str  # pattern | gazetteer | heuristic
    detail: str = ""
    entity_uid: str | None = None  # set when resolved to a known entity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractedRelationship:
    source_text: str
    target_text: str
    type: str
    label: str
    confidence: float
    trigger: str
    trigger_start: int
    trigger_end: int
    sentence: str
    sentence_start: int
    source_uid: str | None = None
    target_uid: str | None = None
    evidence_status: str = "INFERRED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
    insights: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    engine: str = "rule-based-1.0"
    text_length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
            "insights": self.insights,
            "confidence": round(self.confidence, 3),
            "engine": self.engine,
            "text_length": self.text_length,
        }


class NlpEngine(Protocol):
    """Substitution point for a statistical model.

    A spaCy or transformer pipeline can implement this and be selected by
    configuration. No such model is bundled or assumed present here.
    """

    def analyze(self, text: str, gazetteer: "Gazetteer | None" = None) -> ExtractionResult: ...

    def name(self) -> str: ...


# ------------------------------------------------------------------ gazetteer


def normalize(value: str, entity_type: str = "") -> str:
    """Canonical comparison form.

    Phones drop punctuation and the country code so +91-98765 43210 and
    9876543210 collapse together. Vehicles drop separators and case. Names
    lowercase and collapse whitespace.
    """
    v = (value or "").strip()
    if entity_type == "phone":
        digits = re.sub(r"[^\dxX]", "", v)
        if len(digits) > 10 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        return digits.lower()
    if entity_type == "vehicle":
        return re.sub(r"[\s\-]", "", v).upper()
    if entity_type == "transaction":
        return re.sub(r"[\s,]", "", v).lower()
    return re.sub(r"\s+", " ", v).strip().lower().rstrip(".")


class Gazetteer:
    """Known entity names and aliases, for dictionary-based recognition.

    Built from the database so extraction improves as the knowledge graph
    grows: a location named in one FIR is recognised in the next one.
    """

    def __init__(self) -> None:
        self._by_normalized: dict[str, tuple[str, str, str]] = {}  # norm -> (uid, type, display)
        # Single name-parts ("Rahul", "Sharma") -> the uids that use them.
        # Case text routinely drops to a first name after the full name has
        # been introduced, so without this most in-sentence relationships are
        # never extracted. Only unambiguous parts are ever matched.
        self._name_parts: dict[str, set[tuple[str, str, str]]] = {}
        self._max_words = 1

    def add(self, uid: str, entity_type: str, name: str, aliases: list[str] | None = None) -> None:
        for surface in [name, *(aliases or [])]:
            if not surface or len(surface) < 2:
                continue
            key = normalize(surface, entity_type)
            if not key:
                continue
            self._by_normalized.setdefault(key, (uid, entity_type, surface))
            self._max_words = max(self._max_words, len(surface.split()))

            if entity_type == "person":
                parts = [p.strip(".") for p in surface.split()]
                if len(parts) > 1:
                    for part in parts:
                        # Skip initials and very short tokens - "R." is not
                        # distinctive enough to identify anyone.
                        if len(part) < 3:
                            continue
                        self._name_parts.setdefault(part.lower(), set()).add(
                            (uid, entity_type, name)
                        )

    def _unambiguous_part(self, token: str) -> tuple[str, str, str] | None:
        """Resolve a bare name part, but only when exactly one entity claims it."""
        owners = self._name_parts.get(token.lower())
        if not owners:
            return None
        uids = {owner[0] for owner in owners}
        if len(uids) != 1:
            return None  # ambiguous: two people share this name part
        return next(iter(owners))

    def lookup(self, surface: str, entity_type: str = "") -> tuple[str, str, str] | None:
        return self._by_normalized.get(normalize(surface, entity_type))

    def find_in(self, text: str) -> list[ExtractedEntity]:
        """Longest-match-first scan over word n-grams."""
        found: list[ExtractedEntity] = []
        # Token positions so spans map back to original character offsets.
        tokens = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        used: set[int] = set()
        for size in range(min(self._max_words, 6), 0, -1):
            for i in range(len(tokens) - size + 1):
                if any(j in used for j in range(i, i + size)):
                    continue
                start = tokens[i][1]
                end = tokens[i + size - 1][2]
                surface = text[start:end]
                cleaned = surface.strip(".,;:!?()[]\"'")
                if len(cleaned) < 2:
                    continue
                hit = self._by_normalized.get(normalize(cleaned))
                if hit is None:
                    continue
                uid, entity_type, display = hit
                offset = surface.find(cleaned)
                found.append(
                    ExtractedEntity(
                        text=cleaned,
                        type=entity_type,
                        normalized=normalize(cleaned, entity_type),
                        start=start + offset,
                        end=start + offset + len(cleaned),
                        confidence=0.97,
                        method="gazetteer",
                        detail=f"Matched known entity '{display}' already in the knowledge graph",
                        entity_uid=uid,
                    )
                )
                used.update(range(i, i + size))

        # Second pass: bare name parts not already covered by a full match.
        for i, (token, start, end) in enumerate(tokens):
            if i in used:
                continue
            cleaned = token.strip(".,;:!?()[]\"'")
            if len(cleaned) < 3 or not cleaned[0].isupper():
                continue
            hit = self._unambiguous_part(cleaned)
            if hit is None:
                continue
            uid, entity_type, display = hit
            offset = token.find(cleaned)
            found.append(
                ExtractedEntity(
                    text=cleaned,
                    type=entity_type,
                    normalized=normalize(display, entity_type),
                    start=start + offset,
                    end=start + offset + len(cleaned),
                    confidence=0.86,
                    method="gazetteer",
                    detail=(
                        f"Partial name match - resolved to '{display}', the only "
                        f"known entity using this name part"
                    ),
                    entity_uid=uid,
                )
            )
            used.add(i)
        return found

    def __len__(self) -> int:
        return len(self._by_normalized)


# -------------------------------------------------------------- rule engine


_STRUCTURED_PATTERNS: list[tuple[str, re.Pattern, float, str]] = [
    ("phone", P.PHONE, 0.96, "Matches Indian mobile number format"),
    ("vehicle", P.VEHICLE, 0.93, "Matches Indian vehicle registration format"),
    ("transaction", P.CURRENCY, 0.94, "Matches currency amount format"),
    ("case_record", P.CASE_ID, 0.90, "Matches case/FIR identifier format"),
    ("social", P.SOCIAL_HANDLE, 0.92, "Matches social media handle format"),
    ("social", P.EMAIL, 0.90, "Matches email address format"),
    ("phone", P.IMEI, 0.88, "Matches 15-digit device identifier (IMEI) format"),
]


class RuleBasedEngine:
    """The default engine. Deterministic, explainable, no model download."""

    VERSION = "rule-based-1.0"

    def name(self) -> str:
        return self.VERSION

    # -- public ---------------------------------------------------------

    def analyze(self, text: str, gazetteer: Gazetteer | None = None) -> ExtractionResult:
        text = text or ""
        result = ExtractionResult(engine=self.VERSION, text_length=len(text))
        if not text.strip():
            return result

        candidates: list[ExtractedEntity] = []
        candidates += self._structured(text)
        if gazetteer is not None:
            candidates += gazetteer.find_in(text)
        candidates += self._organisations(text)
        candidates += self._persons(text)

        result.entities = self._deduplicate(candidates)
        # Let gazetteer hits inform person/org typing of nearby spans.
        if gazetteer is not None:
            for entity in result.entities:
                if entity.entity_uid is None:
                    hit = gazetteer.lookup(entity.text, entity.type)
                    if hit:
                        entity.entity_uid, entity.type, _ = hit

        result.relationships = self._relationships(text, result.entities)
        result.insights = self._insights(result)
        result.confidence = self._overall_confidence(result)
        return result

    # -- stages ---------------------------------------------------------

    def _structured(self, text: str) -> list[ExtractedEntity]:
        out: list[ExtractedEntity] = []
        for entity_type, pattern, confidence, detail in _STRUCTURED_PATTERNS:
            for match in pattern.finditer(text):
                surface = match.group(0).strip()
                if not surface:
                    continue
                out.append(
                    ExtractedEntity(
                        text=surface,
                        type=entity_type,
                        normalized=normalize(surface, entity_type),
                        start=match.start(),
                        end=match.start() + len(surface),
                        confidence=confidence,
                        method="pattern",
                        detail=detail,
                    )
                )
        # Dates and day labels become event anchors rather than entities.
        for pattern, detail in ((P.DATE, "Absolute date reference"), (P.DAY_LABEL, "Relative day reference")):
            for match in pattern.finditer(text):
                out.append(
                    ExtractedEntity(
                        text=match.group(0),
                        type="event",
                        normalized=normalize(match.group(0)),
                        start=match.start(),
                        end=match.end(),
                        confidence=0.85,
                        method="pattern",
                        detail=detail,
                    )
                )
        return out

    def _organisations(self, text: str) -> list[ExtractedEntity]:
        return [
            ExtractedEntity(
                text=m.group(0).strip(),
                type="organization",
                normalized=normalize(m.group(0)),
                start=m.start(),
                end=m.start() + len(m.group(0).strip()),
                confidence=0.88,
                method="heuristic",
                detail="Capitalised phrase ending in a corporate suffix",
            )
            for m in P.ORG_SUFFIX.finditer(text)
        ]

    def _persons(self, text: str) -> list[ExtractedEntity]:
        out: list[ExtractedEntity] = []

        for m in P.HONORIFIC_NAME.finditer(text):
            name = m.group(1).strip()
            out.append(
                ExtractedEntity(
                    text=name, type="person", normalized=normalize(name),
                    start=m.start(1), end=m.start(1) + len(name),
                    confidence=0.94, method="heuristic",
                    detail="Name preceded by an honorific",
                )
            )

        for m in P.INITIAL_NAME.finditer(text):
            out.append(
                ExtractedEntity(
                    text=m.group(0), type="person", normalized=normalize(m.group(0)),
                    start=m.start(), end=m.end(),
                    confidence=0.80, method="heuristic",
                    detail="Initial-and-surname form (e.g. R. Verma)",
                )
            )

        for m in P.CAPITALISED_NAME.finditer(text):
            surface = m.group(0)
            first = surface.split()[0]
            if first in P.NAME_STOPWORDS:
                continue
            # Reject when every token is a stopword-ish domain term.
            if all(tok in P.NAME_STOPWORDS for tok in surface.split()):
                continue
            # A sentence-initial capitalised pair is weaker evidence.
            sentence_initial = m.start() == 0 or text[max(0, m.start() - 2) : m.start()].strip() in {".", "!", "?", ""}
            out.append(
                ExtractedEntity(
                    text=surface, type="person", normalized=normalize(surface),
                    start=m.start(), end=m.end(),
                    confidence=0.68 if sentence_initial else 0.76,
                    method="heuristic",
                    detail="Sequence of capitalised tokens consistent with a personal name",
                )
            )
        return out

    @staticmethod
    def _deduplicate(candidates: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Resolve overlapping spans: prefer longer, then higher confidence.

        A gazetteer hit on "Shivam Logistics Pvt. Ltd." must beat a bare
        capitalised-name guess at "Shivam Logistics".
        """
        ranked = sorted(
            candidates,
            key=lambda e: (-(e.end - e.start), -e.confidence, e.start),
        )
        kept: list[ExtractedEntity] = []
        for candidate in ranked:
            if any(not (candidate.end <= k.start or candidate.start >= k.end) for k in kept):
                continue
            kept.append(candidate)
        kept.sort(key=lambda e: e.start)
        return kept

    def _relationships(
        self, text: str, entities: list[ExtractedEntity]
    ) -> list[ExtractedRelationship]:
        """Trigger-verb extraction within sentence boundaries.

        For each trigger occurrence, pair the nearest preceding entity with the
        nearest following entity. Staying inside one sentence is what stops the
        extractor from inventing links across unrelated statements.
        """
        out: list[ExtractedRelationship] = []
        for sentence, sentence_start in self._sentences(text):
            in_sentence = [
                e for e in entities
                if e.start >= sentence_start and e.end <= sentence_start + len(sentence)
            ]
            if len(in_sentence) < 2:
                continue
            for trigger in P.RELATION_TRIGGERS:
                for match in trigger["regex"].finditer(sentence):
                    t_start = sentence_start + match.start()
                    t_end = sentence_start + match.end()
                    before = [e for e in in_sentence if e.end <= t_start]
                    after = [e for e in in_sentence if e.start >= t_end]
                    if not before or not after:
                        continue
                    subject = before[-1]
                    obj = after[0]
                    if subject.start == obj.start:
                        continue
                    gap = obj.start - subject.end
                    # Confidence falls off as subject and object drift apart.
                    proximity = max(0.4, 1.0 - (gap / 220.0))
                    confidence = round(
                        min(0.95, 0.55 + 0.35 * proximity)
                        * ((subject.confidence + obj.confidence) / 2),
                        3,
                    )
                    out.append(
                        ExtractedRelationship(
                            source_text=subject.text,
                            target_text=obj.text,
                            type=trigger["type"],
                            label=trigger["label"],
                            confidence=confidence,
                            trigger=match.group(0),
                            trigger_start=t_start,
                            trigger_end=t_end,
                            sentence=sentence.strip(),
                            sentence_start=sentence_start,
                            source_uid=subject.entity_uid,
                            target_uid=obj.entity_uid,
                        )
                    )

                    # Money flows are three-part: payer, amount, payee. Pairing
                    # the payer with only the nearest entity captures the amount
                    # and loses the recipient, which is the investigatively
                    # interesting half. Emit the payer->payee link as well.
                    if trigger["type"] == "TRANSFERRED_MONEY" and obj.type == "transaction":
                        recipients = [
                            e for e in after
                            if e.start > obj.end and e.type in ("organization", "person")
                        ]
                        if recipients:
                            payee = recipients[0]
                            between = sentence[
                                obj.end - sentence_start : payee.start - sentence_start
                            ]
                            # Require an explicit recipient marker so an
                            # unrelated trailing name is not misread as a payee.
                            if re.search(r"\b(?:to|into|towards|in favour of)\b", between, re.I):
                                out.append(
                                    ExtractedRelationship(
                                        source_text=subject.text,
                                        target_text=payee.text,
                                        type="TRANSFERRED_MONEY",
                                        label="Transferred Money",
                                        confidence=round(confidence * 0.97, 3),
                                        trigger=f"{match.group(0)} ... to",
                                        trigger_start=t_start,
                                        trigger_end=t_end,
                                        sentence=sentence.strip(),
                                        sentence_start=sentence_start,
                                        source_uid=subject.entity_uid,
                                        target_uid=payee.entity_uid,
                                    )
                                )
        return self._dedupe_relationships(out)

    @staticmethod
    def _dedupe_relationships(rels: list[ExtractedRelationship]) -> list[ExtractedRelationship]:
        seen: dict[tuple[str, str, str], ExtractedRelationship] = {}
        for r in rels:
            key = (r.source_text.lower(), r.type, r.target_text.lower())
            if key not in seen or r.confidence > seen[key].confidence:
                seen[key] = r
        return sorted(seen.values(), key=lambda r: (-r.confidence, r.trigger_start))

    @staticmethod
    def _sentences(text: str) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        cursor = 0
        for part in P.SENTENCE_SPLIT.split(text):
            index = text.find(part, cursor)
            if index < 0:
                index = cursor
            out.append((part, index))
            cursor = index + len(part)
        return out

    @staticmethod
    def _insights(result: ExtractionResult) -> list[dict[str, Any]]:
        """Observations about the extraction itself - never claims about guilt."""
        insights: list[dict[str, Any]] = []
        by_type: dict[str, int] = {}
        for e in result.entities:
            by_type[e.type] = by_type.get(e.type, 0) + 1

        known = [e for e in result.entities if e.entity_uid]
        if known:
            insights.append({
                "kind": "known_entities",
                "text": (
                    f"{len(known)} of {len(result.entities)} extracted entities already exist "
                    f"in the knowledge graph and will be linked rather than duplicated."
                ),
                "status": "OBSERVED",
                "supporting": [e.text for e in known][:8],
            })
        new_entities = [e for e in result.entities if not e.entity_uid]
        if new_entities:
            insights.append({
                "kind": "new_entities",
                "text": f"{len(new_entities)} extracted entities are not yet in the graph.",
                "status": "INFERRED",
                "supporting": [e.text for e in new_entities][:8],
            })
        if result.relationships:
            insights.append({
                "kind": "relationships",
                "text": (
                    f"{len(result.relationships)} candidate relationships extracted from trigger "
                    f"phrases. All require investigator confirmation before entering the case record."
                ),
                "status": "INFERRED",
                "supporting": [
                    f"{r.source_text} -[{r.label}]-> {r.target_text}" for r in result.relationships
                ][:8],
            })
        low_confidence = [e for e in result.entities if e.confidence < 0.75]
        if low_confidence:
            insights.append({
                "kind": "review_needed",
                "text": (
                    f"{len(low_confidence)} extractions fell below the 0.75 confidence threshold "
                    f"and are flagged for manual review."
                ),
                "status": "INFERRED",
                "supporting": [f"{e.text} ({e.confidence:.2f})" for e in low_confidence][:8],
            })
        return insights

    @staticmethod
    def _overall_confidence(result: ExtractionResult) -> float:
        scores = [e.confidence for e in result.entities] + [
            r.confidence for r in result.relationships
        ]
        return sum(scores) / len(scores) if scores else 0.0


DEFAULT_ENGINE = RuleBasedEngine()
