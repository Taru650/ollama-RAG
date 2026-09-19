"""Classify a docx run's declared font as legacy-Hindi-encoded or not.

Confirmed from the two real sample letters: runs declared as
"DevLys 040" contain Kruti-Dev-encoded bytes (not a distinct DevLys
mapping) -- the rFonts label names a *font*, not a reliable encoding
promise. So this resolver only answers "does this font name usually
mean legacy 8-bit Hindi encoding", and the decoder still validates the
result with the plausibility scorer rather than trusting the label
blindly.
"""
from __future__ import annotations

# Font names observed (or commonly documented) as legacy 8-bit Hindi
# glyph-encoded fonts that must be routed through kru2uni.
_LEGACY_DEVANAGARI_FONT_PREFIXES = (
    "kruti dev",
    "devlys",
    "chanakya",
    "shusha",
    "walkman",
    "shivaji",
    "krishna",
    "amar ujala",
    "dv-",
)

# Font names known to already be Unicode (Mangal, Nirmala UI, ...) or
# genuinely Latin (English letterhead text, officer names, emails) --
# must NEVER be routed through the legacy decoder.
_PASSTHROUGH_FONT_PREFIXES = (
    "mangal",
    "nirmala",
    "times new roman",
    "calibri",
    "cambria",
    "arial",
    "tahoma",
    "segoe",
    "consolas",
    "verdana",
    "aparajita",
    "utsaah",
    "kokila",
)


def is_legacy_devanagari_font(font_name: str | None) -> bool:
    """Return True if this rFonts name should be routed through kru2uni."""
    if not font_name:
        return False
    name = font_name.strip().lower()
    if any(name.startswith(p) for p in _PASSTHROUGH_FONT_PREFIXES):
        return False
    return any(name.startswith(p) for p in _LEGACY_DEVANAGARI_FONT_PREFIXES)
