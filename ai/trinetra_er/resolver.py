"""Entity resolution - identifying records that may describe the same entity.

Design constraints that come from the problem domain, not from convenience:

  * Nothing merges automatically. The resolver only ever proposes; an
    authorised investigator accepts or rejects.
  * Every score decomposes into named factors with their own contributions,
    so "0.87" is never presented without saying what produced it.
  * Comparison is blocked by entity type - a phone is never compared to a
    person - and within type by a cheap key, so the pass is O(n) in practice
    rather than O(n^2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------- primitives


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


def edit_ratio(a: str, b: str) -> float:
    """1.0 = identical, 0.0 = entirely different."""
    if not a and not b:
        return 1.0
    longest = max(len(a), len(b))
    return 1.0 - (levenshtein(a, b) / longest) if longest else 0.0


def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    window = max(len(a), len(b)) // 2 - 1
    window = max(window, 0)
    a_flags = [False] * len(a)
    b_flags = [False] * len(b)
    matches = 0
    for i, ca in enumerate(a):
        start = max(0, i - window)
        end = min(i + window + 1, len(b))
        for j in range(start, end):
            if not b_flags[j] and b[j] == ca:
                a_flags[i] = b_flags[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    transpositions = 0
    k = 0
    for i, flag in enumerate(a_flags):
        if not flag:
            continue
        while not b_flags[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1
    transpositions //= 2
    return (matches / len(a) + matches / len(b) + (matches - transpositions) / matches) / 3.0


def jaro_winkler(a: str, b: str, prefix_weight: float = 0.1) -> float:
    """Jaro with a bonus for shared prefixes - suits personal names."""
    base = jaro(a, b)
    prefix = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        prefix += 1
        if prefix == 4:
            break
    return base + prefix * prefix_weight * (1 - base)


def soundex(name: str) -> str:
    """Classic Soundex - a coarse phonetic key for blocking and scoring.

    Kept deliberately simple: it is used as one signal among several, never
    as a decision on its own. It suits the Latin-script transliterations of
    Indian names that appear in case records.
    """
    name = re.sub(r"[^A-Za-z]", "", name).upper()
    if not name:
        return ""
    codes = {
        **dict.fromkeys("BFPV", "1"),
        **dict.fromkeys("CGJKQSXZ", "2"),
        **dict.fromkeys("DT", "3"),
        "L": "4",
        **dict.fromkeys("MN", "5"),
        "R": "6",
    }
    result = name[0]
    previous = codes.get(name[0], "")
    for char in name[1:]:
        code = codes.get(char, "")
        if code and code != previous:
            result += code
        if char not in "HW":
            previous = code
    return (result + "000")[:4]


def initials_of(name: str) -> str:
    return "".join(part[0] for part in re.split(r"[\s.]+", name) if part).upper()


def is_abbreviation_of(short: str, full: str) -> bool:
    """True when `short` is a plausible abbreviation of `full`.

    Recognises the redaction styles that dominate case files:
        "R. Sharma"  <- "Rahul Sharma"
        "Rahul S."   <- "Rahul Sharma"
        "R.S."       <- "Rahul Sharma"
    """
    short_parts = [p for p in re.split(r"[\s.]+", short.strip()) if p]
    full_parts = [p for p in re.split(r"[\s.]+", full.strip()) if p]
    if not short_parts or not full_parts or len(short_parts) > len(full_parts):
        return False
    # An identical string is not an abbreviation of itself. Without this, two
    # equal names score a corroboration bonus they have not earned.
    if short.strip().lower() == full.strip().lower():
        return False
    # Require a genuine contraction: at least one single-letter initial, or
    # fewer name parts than the full form.
    if len(short_parts) == len(full_parts) and not any(len(p) == 1 for p in short_parts):
        return False
    # Compare from the right so surnames align even when middle names differ.
    for s, f in zip(reversed(short_parts), reversed(full_parts)):
        s_low, f_low = s.lower(), f.lower()
        if len(s_low) == 1:
            if s_low != f_low[0]:
                return False
        elif s_low != f_low:
            return False
    return True


# ----------------------------------------------------------------- scoring


@dataclass
class MatchFactor:
    key: str
    label: str
    weight: float
    score: float           # 0..1 for this signal
    detail: str

    @property
    def contribution(self) -> float:
        return round(self.weight * self.score, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "weight": self.weight,
            "score": round(self.score, 4),
            "contribution": self.contribution,
            "detail": self.detail,
        }


@dataclass
class MatchCandidate:
    uid_a: str
    uid_b: str
    name_a: str
    name_b: str
    entity_type: str
    confidence: float
    factors: list[MatchFactor] = field(default_factory=list)
    requires_review: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_a": self.uid_a,
            "uid_b": self.uid_b,
            "name_a": self.name_a,
            "name_b": self.name_b,
            "entity_type": self.entity_type,
            "confidence": round(self.confidence, 4),
            "factors": [f.to_dict() for f in self.factors],
            "requires_review": self.requires_review,
            "status": "POTENTIAL MATCH",
        }


@dataclass
class ResolutionInput:
    """A comparable projection of an entity, independent of the ORM."""

    uid: str
    type: str
    name: str
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    neighbour_uids: set[str] = field(default_factory=set)
    case_uids: set[str] = field(default_factory=set)


class EntityResolver:
    """Multi-signal resolver producing reviewable candidates."""

    VERSION = "er-1.0"

    # Weights sum to 1.0. Stated openly because the score has to be defensible.
    WEIGHTS = {
        "name_similarity": 0.26,
        "abbreviation": 0.14,
        "phonetic": 0.05,
        "shared_attributes": 0.33,
        "shared_neighbours": 0.14,
        "shared_cases": 0.08,
    }

    # How strongly a shared identifier implies the same underlying entity.
    # These are not all equal: an ID-proof reference used to buy a SIM is far
    # closer to unique than a shared address. An alias is *expected* to carry a
    # different name, so identifier evidence must be able to carry a match on
    # its own rather than being outvoted by name dissimilarity.
    IDENTIFIER_STRENGTH = {
        "id_proof": 0.80,
        "device_id": 0.78,
        "vehicle": 0.75,
        "phone": 0.72,
        "email": 0.65,
        "address": 0.45,
        "dob": 0.35,
    }

    # Identifiers that effectively belong to exactly one individual. Shared
    # possession of these is strong alias evidence on its own; everything else
    # (vehicles, phones) is routinely shared and needs corroboration.
    EXCLUSIVE_IDENTIFIERS = {"id_proof", "device_id"}

    # Below this, a pair is not worth an investigator's attention.
    REVIEW_THRESHOLD = 0.55

    def __init__(self, review_threshold: float | None = None) -> None:
        self.review_threshold = (
            review_threshold if review_threshold is not None else self.REVIEW_THRESHOLD
        )

    # -- blocking -------------------------------------------------------

    @staticmethod
    def _blocking_keys(entity: ResolutionInput) -> set[str]:
        """Cheap keys that any true match must share at least one of."""
        keys: set[str] = set()
        for surface in [entity.name, *entity.aliases]:
            cleaned = re.sub(r"[^A-Za-z0-9\s]", "", surface).strip()
            if not cleaned:
                continue
            if entity.type == "person":
                parts = cleaned.split()
                # Surname phonetic key, plus each initial, so "R. Sharma" and
                # "Rahul Sharma" land in the same block.
                if parts:
                    keys.add(f"snd:{soundex(parts[-1])}")
                    keys.add(f"ini:{parts[0][0].upper()}{parts[-1][0].upper()}")
            else:
                keys.add(f"pre:{cleaned[:4].lower()}")
                keys.add(f"len:{entity.type}:{len(cleaned)}")

        # Identifier blocking. Two records sharing a phone, vehicle, ID proof
        # or device are the single strongest alias signal there is, and they
        # routinely carry completely different names - which is exactly the
        # case that name-based blocking would never surface.
        for key in ("phone", "vehicle", "id_proof", "email", "device_id"):
            value = entity.attributes.get(key)
            if value:
                keys.add(f"attr:{key}:{str(value).strip().lower()}")
        return keys

    def candidate_pairs(
        self, entities: list[ResolutionInput]
    ) -> list[tuple[ResolutionInput, ResolutionInput]]:
        buckets: dict[str, list[ResolutionInput]] = {}
        for entity in entities:
            for key in self._blocking_keys(entity):
                buckets.setdefault(f"{entity.type}|{key}", []).append(entity)

        seen: set[tuple[str, str]] = set()
        pairs: list[tuple[ResolutionInput, ResolutionInput]] = []
        for bucket in buckets.values():
            if len(bucket) < 2 or len(bucket) > 60:
                continue  # oversized blocks are uninformative, not worth O(n^2)
            for i in range(len(bucket)):
                for j in range(i + 1, len(bucket)):
                    a, b = bucket[i], bucket[j]
                    if a.uid == b.uid:
                        continue
                    key = tuple(sorted((a.uid, b.uid)))
                    if key in seen:
                        continue
                    seen.add(key)
                    pairs.append((a, b))
        return pairs

    # -- scoring --------------------------------------------------------

    def score_pair(self, a: ResolutionInput, b: ResolutionInput) -> MatchCandidate:
        factors: list[MatchFactor] = []
        a_surfaces = [a.name, *a.aliases]
        b_surfaces = [b.name, *b.aliases]

        # 1. Best string similarity across all surface forms.
        best_sim, best_pair = 0.0, (a.name, b.name)
        for sa in a_surfaces:
            for sb in b_surfaces:
                sim = max(jaro_winkler(sa.lower(), sb.lower()), edit_ratio(sa.lower(), sb.lower()))
                if sim > best_sim:
                    best_sim, best_pair = sim, (sa, sb)
        factors.append(
            MatchFactor(
                "name_similarity", "Name similarity", self.WEIGHTS["name_similarity"], best_sim,
                f"Closest surface forms {best_pair[0]!r} vs {best_pair[1]!r} score {best_sim:.2f}",
            )
        )

        # 2. Abbreviation / initial form.
        abbrev = any(
            is_abbreviation_of(sa, sb) or is_abbreviation_of(sb, sa)
            for sa in a_surfaces for sb in b_surfaces
        )
        abbrev_detail = "No abbreviation relationship detected"
        if abbrev:
            for sa in a_surfaces:
                for sb in b_surfaces:
                    if is_abbreviation_of(sa, sb):
                        abbrev_detail = f"{sa!r} is a valid abbreviation of {sb!r}"
                        break
                    if is_abbreviation_of(sb, sa):
                        abbrev_detail = f"{sb!r} is a valid abbreviation of {sa!r}"
                        break
        factors.append(
            MatchFactor(
                "abbreviation", "Abbreviation / initial form",
                self.WEIGHTS["abbreviation"], 1.0 if abbrev else 0.0, abbrev_detail,
            )
        )

        # 3. Phonetic agreement on the last name part.
        pa = soundex(a.name.split()[-1]) if a.name.split() else ""
        pb = soundex(b.name.split()[-1]) if b.name.split() else ""
        phonetic = 1.0 if (pa and pa == pb) else 0.0
        factors.append(
            MatchFactor(
                "phonetic", "Phonetic key", self.WEIGHTS["phonetic"], phonetic,
                f"Soundex {pa or 'n/a'} vs {pb or 'n/a'}"
                + (" - match" if phonetic else " - differ"),
            )
        )

        # 4. Shared identifying attributes, scored by identifier strength
        #    rather than by count - one shared ID proof outweighs two shared
        #    weak attributes.
        shared_attrs = self._shared_attributes(a, b)
        strengths = [self.IDENTIFIER_STRENGTH.get(k, 0.4) for k, _ in shared_attrs]
        if strengths:
            best = max(strengths)
            # Additional corroborating identifiers add a diminishing bonus.
            attr_score = min(1.0, best + 0.06 * (len(strengths) - 1))
        else:
            attr_score = 0.0
        factors.append(
            MatchFactor(
                "shared_attributes", "Shared identifiers",
                self.WEIGHTS["shared_attributes"], attr_score,
                ("Shares " + ", ".join(f"{k}={v}" for k, v in shared_attrs)) if shared_attrs
                else "No identifying attributes in common",
            )
        )

        # 5. Shared graph neighbours.
        shared_neighbours = a.neighbour_uids & b.neighbour_uids
        neighbour_score = min(1.0, len(shared_neighbours) / 3.0)
        factors.append(
            MatchFactor(
                "shared_neighbours", "Shared connections",
                self.WEIGHTS["shared_neighbours"], neighbour_score,
                f"{len(shared_neighbours)} connection(s) in common"
                + (f": {', '.join(sorted(shared_neighbours)[:4])}" if shared_neighbours else ""),
            )
        )

        # 6. Co-occurrence in the same cases.
        shared_cases = a.case_uids & b.case_uids
        case_score = min(1.0, len(shared_cases) / 2.0)
        factors.append(
            MatchFactor(
                "shared_cases", "Case co-occurrence", self.WEIGHTS["shared_cases"], case_score,
                f"{len(shared_cases)} shared case(s)"
                + (f": {', '.join(sorted(shared_cases))}" if shared_cases else ""),
            )
        )

        confidence = sum(f.contribution for f in factors)

        # A shared near-unique identifier establishes a minimum plausibility on
        # its own. Two records naming the same ID proof are a lead worth review
        # even when the names share nothing - which is precisely the shape an
        # alias takes. The floor is recorded as its own factor so the reason
        # the score rose is visible rather than hidden in the arithmetic.
        # Identifiers differ in how exclusively they belong to one person. An
        # ID-proof reference or device fingerprint effectively identifies an
        # individual, so one is enough. A vehicle or phone is routinely shared
        # between family members, colleagues and co-owners - a single one is a
        # lead worth noting but not grounds for a high-confidence alias claim,
        # so it only carries a floor when something else corroborates it.
        strong = [(k, v) for k, v in shared_attrs if self.IDENTIFIER_STRENGTH.get(k, 0) >= 0.65]
        exclusive = [(k, v) for k, v in strong if k in self.EXCLUSIVE_IDENTIFIERS]
        corroborated_by_other = abbrev or neighbour_score > 0 or case_score > 0 or best_sim >= 0.72

        floor_applies = bool(exclusive) or len(strong) > 1 or (strong and corroborated_by_other)
        if floor_applies:
            floor = max(self.IDENTIFIER_STRENGTH[k] for k, _ in strong)
            if len(strong) > 1:
                floor = min(0.92, floor + 0.06 * (len(strong) - 1))
            if not exclusive and len(strong) == 1:
                # Shareable identifier standing alone with weak corroboration.
                floor *= 0.82
            if floor > confidence:
                factors.append(
                    MatchFactor(
                        "identifier_floor", "Strong identifier floor", 0.0, 0.0,
                        f"Shared {', '.join(k for k, _ in strong)} raises minimum "
                        f"confidence to {floor:.2f} independently of name similarity"
                        + ("" if exclusive or len(strong) > 1
                           else " (reduced: this identifier can legitimately be shared)"),
                    )
                )
                confidence = floor

        # A high string score alone is not enough: two unrelated people can
        # share a common Indian surname. Require corroboration from at least
        # one non-string signal before a pair can reach high confidence.
        corroborated = abbrev or attr_score > 0 or neighbour_score > 0 or case_score > 0
        if not corroborated:
            confidence = min(confidence, 0.62)
            factors.append(
                MatchFactor(
                    "corroboration", "Corroborating evidence", 0.0, 0.0,
                    "Name similarity only - no shared identifiers, connections or cases. "
                    "Confidence capped pending further evidence.",
                )
            )

        return MatchCandidate(
            uid_a=a.uid, uid_b=b.uid, name_a=a.name, name_b=b.name,
            entity_type=a.type, confidence=min(confidence, 0.99), factors=factors,
            requires_review=True,
        )

    @classmethod
    def _shared_attributes(
        cls, a: ResolutionInput, b: ResolutionInput
    ) -> list[tuple[str, str]]:
        """Identifiers present and equal on both records, as (key, value)."""
        shared: list[tuple[str, str]] = []
        for key in cls.IDENTIFIER_STRENGTH:
            va, vb = a.attributes.get(key), b.attributes.get(key)
            if va and vb and str(va).strip().lower() == str(vb).strip().lower():
                shared.append((key, str(va)))
        return shared

    # -- entry point ----------------------------------------------------

    def find_candidates(self, entities: list[ResolutionInput]) -> list[MatchCandidate]:
        """Return reviewable candidates, most confident first."""
        results = [
            candidate
            for a, b in self.candidate_pairs(entities)
            if (candidate := self.score_pair(a, b)).confidence >= self.review_threshold
        ]
        results.sort(key=lambda c: -c.confidence)
        return results
