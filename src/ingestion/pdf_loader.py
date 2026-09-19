"""PDF loader: text-layer extraction with an OCR fallback for
scanned/image-only pages.

Two unrelated problems, handled by two unrelated mechanisms:
- A real text layer in a legacy Hindi font (e.g. a Kruti Dev .docx
  printed to PDF) -> same per-span legacy-font decode as docx_loader.
- No usable text layer (a scanned page) -> render the page to an
  image and OCR it (src/ingestion/ocr.py). Tesseract's Hindi model
  outputs Unicode directly, so none of the legacy-font machinery
  applies to OCR'd text -- its failure mode is misread characters,
  not wrong-encoding-table mojibake, so it carries Tesseract's own
  confidence score instead of the plausibility score.

Returns the same DecodedLine type as docx_loader so segmentation and
metadata extraction work unmodified on either source.
"""
from __future__ import annotations

import fitz  # PyMuPDF
from PIL import Image

from .docx_loader import DecodedLine
from .legacy_fonts.font_family_resolver import is_legacy_devanagari_font
from .legacy_fonts.run_decoder import RunDecodeResult, decode_run
from .ocr import ocr_image

MIN_TEXT_LAYER_CHARS = 20  # below this, treat the page as scanned


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


def _extract_text_layer_lines(page: fitz.Page) -> list[DecodedLine]:
    lines: list[DecodedLine] = []
    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            groups = _group_spans_by_classification(spans)
            results = [decode_run(text, font) for text, font in groups]
            decoded = "".join(r.text for r in results)
            if decoded.strip():
                lines.append(DecodedLine(text=decoded, page_break_before=False, run_results=results))
    return lines


def _ocr_page_lines(page: fitz.Page, dpi: int = 300) -> list[DecodedLine]:
    pixmap = page.get_pixmap(dpi=dpi)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    result = ocr_image(image)

    lines: list[DecodedLine] = []
    for i, raw_line in enumerate(result.text.splitlines()):
        if not raw_line.strip():
            continue
        fake_run = RunDecodeResult(
            text=raw_line,
            font_name="OCR (tesseract hin+eng)",
            routed_through_legacy_decoder=False,
            plausibility=result.mean_confidence / 100.0,
        )
        lines.append(DecodedLine(
            text=raw_line,
            page_break_before=(i == 0),
            run_results=[fake_run],
        ))
    return lines


def load_pdf_lines(path: str) -> list[DecodedLine]:
    doc = fitz.open(path)
    lines: list[DecodedLine] = []
    for page in doc:
        page_lines = _extract_text_layer_lines(page)
        text_layer_chars = sum(len(l.text.strip()) for l in page_lines)

        if text_layer_chars < MIN_TEXT_LAYER_CHARS:
            page_lines = _ocr_page_lines(page)
        elif page_lines:
            page_lines[0] = DecodedLine(
                text=page_lines[0].text,
                page_break_before=True,
                run_results=page_lines[0].run_results,
            )

        lines.extend(page_lines)
    return lines
