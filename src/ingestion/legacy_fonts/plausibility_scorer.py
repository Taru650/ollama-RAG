"""Score decoded text for how plausible it is as real Hindi.

Used as an audit signal, not a gate: ingestion records the score per
run/document so a human can spot a bad conversion (e.g. a font we
mis-classified) instead of it silently passing through.
"""
from __future__ import annotations

import re

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_LETTERISH_RE = re.compile(r"[^\s\d.,;:\-/()\[\]]")

# Combining marks (matras, virama, anusvara/visarga/candrabindu, nukta)
# that are only valid immediately after a base consonant/vowel. One
# appearing at the start of a token (nothing base before it) is a
# strong signal of malformed/mojibake Devanagari -- e.g. a matra that
# should have been reordered onto its consonant but wasn't.
_COMBINING_MARKS = set(
    "़ािीुूृॄॅॆे"
    "ैॉॊोौ्ंःँ"
)

# Common words in Hindi government correspondence -- deliberately small
# and high-precision (structural/formal vocabulary), not a general
# dictionary.
_COMMON_WORDS = {
    "सेवा", "विषय", "दिनांक", "पत्रांक", "कार्यालय", "जिला", "समाहरणालय",
    "आदेश", "अनुरोध", "प्रतिलिपि", "महोदय", "महाशय", "विभाग", "पदाधिकारी",
    "संबंध", "अधिकारी", "प्रेषक", "भवदीय", "विश्वासभाजन", "आवश्यक",
    "कार्यवाही", "प्रबंधक", "अग्रसारित", "अनुसार", "निर्देश", "स्थापना",
}


def devanagari_ratio(text: str) -> float:
    """Fraction of non-whitespace/punctuation chars that are Devanagari."""
    letterish = _LETTERISH_RE.findall(text)
    if not letterish:
        return 0.0
    devanagari = _DEVANAGARI_RE.findall(text)
    return len(devanagari) / len(letterish)


def common_word_hits(text: str) -> int:
    words = re.findall(r"[ऀ-ॿ]+", text)
    return sum(1 for w in words if w in _COMMON_WORDS)


def malformed_combining_mark_ratio(text: str) -> float:
    """Fraction of Devanagari 'words' that start with a combining mark.

    A matra/virama/anusvara at the start of a token means it has no
    base consonant to attach to -- almost always a sign of a botched
    conversion (e.g. a matra that should have been reordered onto the
    following/preceding consonant but wasn't).
    """
    words = re.findall(r"[ऀ-ॿ]+", text)
    if not words:
        return 0.0
    malformed = sum(1 for w in words if w and w[0] in _COMBINING_MARKS)
    return malformed / len(words)


def plausibility_score(text: str) -> float:
    """0..1 heuristic: higher means "looks like real Hindi text"."""
    if not text.strip():
        return 1.0  # empty/whitespace-only runs are never a problem
    ratio = devanagari_ratio(text)
    if ratio == 0.0:
        # Pure Latin/ASCII text (e.g. an English name) is also fine --
        # this function only flags text that looks like neither
        # coherent Devanagari nor coherent Latin (i.e. mojibake).
        return 1.0
    malformed_penalty = malformed_combining_mark_ratio(text) * 0.6
    bonus = min(common_word_hits(text) * 0.05, 0.3)
    return max(min(ratio + bonus - malformed_penalty, 1.0), 0.0)
