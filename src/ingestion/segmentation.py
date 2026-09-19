"""Split a decoded document into one or more logical letters.

Real finding from the sample corpus: the naive assumption ("dedup by a
*change* in पत्रांक/दिनांक") does not work, because in practice these
reference-number/date fields are usually left as blank template dashes
("पत्रांक--------------------/दिनांक--------------------") for a human
to fill in by hand -- they never change. What *does* reliably repeat,
once per letter, is the structural header block itself: a letterhead
line followed shortly by that blank पत्रांक/दिनांक placeholder line,
followed by "सेवा में," and "विषय :-". So boundaries are anchored on
recurrence of that placeholder line, self-bootstrapped by frequency
(no hardcoded office name), not by field-value changes.

Confirmed on the real files: the banking-cell sample has ~45 distinct
anchor recurrences (correcting an earlier, wrong "~6 letters" visual
estimate), while the disciplinary-order sample has zero recurring
anchors and correctly stays a single record.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .docx_loader import DecodedLine

_REF_DATE_WORDS = ("पत्रांक", "दिनांक")
_SUBJECT_RE = re.compile(r"^\s*विषय\b")
_SERVICE_RE = re.compile(r"सेवा\s*में")
_MIN_ANCHOR_FREQUENCY = 3
_LOOKBACK = 2


@dataclass
class LetterSegment:
    start_line: int
    end_line: int  # inclusive
    matched_subject: bool
    matched_service_to: bool

    def text(self, lines: list[DecodedLine]) -> str:
        return "\n".join(l.text for l in lines[self.start_line:self.end_line + 1])


@dataclass
class SegmentationReport:
    segments: list[LetterSegment] = field(default_factory=list)
    anchor_line_indices: list[int] = field(default_factory=list)
    anchor_text: str | None = None
    gated_as_single_record: bool = True


def _line_frequencies(lines: list[DecodedLine]) -> dict[str, int]:
    freq: dict[str, int] = {}
    for line in lines:
        text = line.text.strip()
        if len(text) > 4:
            freq[text] = freq.get(text, 0) + 1
    return freq


def _find_anchor_indices(lines: list[DecodedLine]) -> tuple[list[int], str | None]:
    freq = _line_frequencies(lines)
    anchor_candidates = {
        text: count for text, count in freq.items()
        if count >= _MIN_ANCHOR_FREQUENCY
        and all(word in text for word in _REF_DATE_WORDS)
    }
    if not anchor_candidates:
        return [], None
    # Most frequent candidate is the real placeholder line (in case of
    # near-duplicate formatting variants with different dot counts).
    anchor_text = max(anchor_candidates, key=anchor_candidates.get)
    indices = [i for i, l in enumerate(lines) if l.text.strip() == anchor_text]
    return indices, anchor_text


def segment_letters(lines: list[DecodedLine]) -> SegmentationReport:
    """Split decoded lines into one or more letters.

    Gate: if the recurring-placeholder anchor pattern doesn't repeat
    at least twice, the whole document is treated as a single letter
    (matches disciplinary-order-style single long documents).
    """
    if not lines:
        return SegmentationReport()

    anchor_indices, anchor_text = _find_anchor_indices(lines)

    if len(anchor_indices) < 2:
        segment = LetterSegment(
            start_line=0,
            end_line=len(lines) - 1,
            matched_subject=any(_SUBJECT_RE.search(l.text) for l in lines),
            matched_service_to=any(_SERVICE_RE.search(l.text) for l in lines),
        )
        return SegmentationReport(
            segments=[segment],
            anchor_line_indices=anchor_indices,
            anchor_text=anchor_text,
            gated_as_single_record=True,
        )

    segments: list[LetterSegment] = []
    prev_end = -1
    for i, anchor_idx in enumerate(anchor_indices):
        start = max(prev_end + 1, anchor_idx - _LOOKBACK)
        next_anchor = anchor_indices[i + 1] if i + 1 < len(anchor_indices) else len(lines)
        end = max(start, next_anchor - _LOOKBACK - 1) if i + 1 < len(anchor_indices) else len(lines) - 1
        window = lines[start:end + 1]
        segments.append(LetterSegment(
            start_line=start,
            end_line=end,
            matched_subject=any(_SUBJECT_RE.search(l.text) for l in window),
            matched_service_to=any(_SERVICE_RE.search(l.text) for l in window),
        ))
        prev_end = end

    return SegmentationReport(
        segments=segments,
        anchor_line_indices=anchor_indices,
        anchor_text=anchor_text,
        gated_as_single_record=False,
    )
