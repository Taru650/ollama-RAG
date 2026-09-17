"""PDF loader for text-layer PDFs (e.g. a legacy-font .docx printed to
PDF, or an already-Unicode PDF). Not exercised against a real sample
in this pass -- both real letters were .docx -- so treat this as
best-effort until validated against an actual PDF from the corpus.

Scanned/image-only PDFs need OCR, which is out of scope for this pass
(see project plan); this loader only reads an existing text layer.
"""
from __future__ import annotations

import fitz  # PyMuPDF

from .legacy_fonts.font_family_resolver import is_legacy_devanagari_font
from .legacy_fonts.run_decoder import decode_run


def _group_spans_by_classification(spans: list[dict]) -> list[tuple[str, str | None]]:
    groups: list[tuple[str, str | None]] = []
    current_text = ""
    current_font: str | None = None
    current_is_legacy: bool | None = None
    for span in spans:
        text = span.get("text", "")
        if not text:
            continue
        font_name = span.get("font")
        is_legacy = is_legacy_devanagari_font(font_name)
        if current_is_legacy is None or is_legacy == current_is_legacy:
            current_text += text
            current_font = current_font or font_name
        else:
            groups.append((current_text, current_font))
            current_text = text
            current_font = font_name
        current_is_legacy = is_legacy
    if current_text:
        groups.append((current_text, current_font))
    return groups


def load_pdf_lines(path: str) -> list[str]:
    doc = fitz.open(path)
    lines: list[str] = []
    for page in doc:
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                groups = _group_spans_by_classification(spans)
                decoded = "".join(decode_run(text, font).text for text, font in groups)
                if decoded.strip():
                    lines.append(decoded)
    return lines
