"""Regex-based metadata extraction from a decoded, segmented letter.

Deliberately not ML-based: government letter fields (विषय, पत्रांक,
दिनांक, सेवा में, प्रेषक, प्रतिलिपि) are structurally labeled, so
pattern matching is both simpler and more auditable than training a
classifier on a two-document corpus.

Fields that aren't actually filled in the source (e.g. a पत्रांक left
as blank template dashes) come back as None -- per the project's
anti-hallucination rule, we never guess or synthesize a value that
isn't really there.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

_SUBJECT_RE = re.compile(r"^\s*विषय\s*[:\-।]*\s*(.*)$")
_CONTEXT_RE = re.compile(r"^\s*प्रसंग\s*[:\-।]*\s*(.*)$")
_SERVICE_TO_RE = re.compile(r"सेवा\s*में")
_SENDER_RE = re.compile(r"^\s*प्रेषक\s*[,:]*\s*$")
_COPY_TO_RE = re.compile(r"^\s*प्रतिलिपि\s*[:\-]*\s*(.*)$")
_REF_DATE_RE = re.compile(r"पत्रांक\s*[:\-.]*\s*([^\s/]*)\s*/?\s*दिनांक\s*[:\-.]*\s*(\S*)")

_PLACEHOLDER_RE = re.compile(r"^[.\-_\s]*$")

_DISCIPLINARY_KEYWORDS = ("आदेश", "आरोप", "अभिकथन", "निलंबित", "दोषी")
_FORWARDING_KEYWORDS = ("अग्रसारित", "अनुरोध", "प्रेषित", "अग्रलेख")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _is_placeholder(value: str | None) -> bool:
    return value is None or bool(_PLACEHOLDER_RE.match(value))


@dataclass
class ExtractedMetadata:
    subject: str | None = None
    context_reference: str | None = None
    reference_number: str | None = None
    reference_date: str | None = None
    recipient_designation: str | None = None
    sender_designation: str | None = None
    copy_to: list[str] = field(default_factory=list)
    letter_type: str = "general_correspondence"
    field_confidence: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def extract_metadata(lines: list[str]) -> ExtractedMetadata:
    """Extract structured fields from a letter's decoded text lines."""
    meta = ExtractedMetadata()
    confidence: dict[str, bool] = {}

    for i, line in enumerate(lines):
        if meta.subject is None:
            m = _SUBJECT_RE.match(line)
            if m:
                meta.subject = _clean(m.group(1))
                confidence["subject"] = meta.subject is not None

        if meta.context_reference is None:
            m = _CONTEXT_RE.match(line)
            if m:
                meta.context_reference = _clean(m.group(1))
                confidence["context_reference"] = meta.context_reference is not None

        if meta.reference_number is None and meta.reference_date is None:
            m = _REF_DATE_RE.search(line)
            if m:
                ref, date = m.group(1), m.group(2)
                meta.reference_number = None if _is_placeholder(ref) else ref
                meta.reference_date = None if _is_placeholder(date) else date
                confidence["reference_number"] = meta.reference_number is not None
                confidence["reference_date"] = meta.reference_date is not None

        if meta.recipient_designation is None and _SERVICE_TO_RE.search(line):
            following = []
            for nxt in lines[i + 1:i + 4]:
                if not nxt.strip() or _SUBJECT_RE.match(nxt) or _CONTEXT_RE.match(nxt):
                    break
                following.append(nxt.strip())
            meta.recipient_designation = _clean(" ".join(following)) if following else None
            confidence["recipient_designation"] = meta.recipient_designation is not None

        if meta.sender_designation is None and _SENDER_RE.match(line):
            following = []
            for nxt in lines[i + 1:i + 4]:
                if not nxt.strip() or _SERVICE_TO_RE.search(nxt):
                    break
                following.append(nxt.strip())
            meta.sender_designation = _clean(" ".join(following)) if following else None
            confidence["sender_designation"] = meta.sender_designation is not None

        m = _COPY_TO_RE.match(line)
        if m:
            entry = _clean(m.group(1))
            if entry:
                meta.copy_to.append(entry)

    full_text = "\n".join(lines)
    if any(kw in full_text for kw in _DISCIPLINARY_KEYWORDS):
        meta.letter_type = "disciplinary_order"
    elif any(kw in full_text for kw in _FORWARDING_KEYWORDS):
        meta.letter_type = "forwarding_request"

    meta.field_confidence = confidence
    return meta
