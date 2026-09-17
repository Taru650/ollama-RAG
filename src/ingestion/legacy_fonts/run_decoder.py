"""Per-run decode decision: legacy Hindi font -> Unicode, or passthrough."""
from __future__ import annotations

from dataclasses import dataclass

from .font_family_resolver import is_legacy_devanagari_font
from .kru2uni import kru2uni
from .plausibility_scorer import plausibility_score


@dataclass
class RunDecodeResult:
    text: str
    font_name: str | None
    routed_through_legacy_decoder: bool
    plausibility: float


def decode_run(raw_text: str, font_name: str | None) -> RunDecodeResult:
    """Decode a single docx run's text given its declared font.

    Only routes through the legacy-font converter when the font name
    looks like a legacy 8-bit Hindi font family; anything else
    (Unicode Devanagari fonts like Mangal, or genuine Latin fonts) is
    passed through unchanged.
    """
    if is_legacy_devanagari_font(font_name):
        decoded = kru2uni(raw_text)
        return RunDecodeResult(
            text=decoded,
            font_name=font_name,
            routed_through_legacy_decoder=True,
            plausibility=plausibility_score(decoded),
        )
    return RunDecodeResult(
        text=raw_text,
        font_name=font_name,
        routed_through_legacy_decoder=False,
        plausibility=plausibility_score(raw_text),
    )
