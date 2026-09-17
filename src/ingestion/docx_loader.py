"""Load a .docx file into an ordered list of decoded logical lines.

Walks the document body in document order across both paragraphs and
tables (the disciplinary-order sample uses a table for its letterhead
block, so a paragraph-only walk would silently drop it). Each run is
decoded individually via ``legacy_fonts.run_decoder`` based on its own
declared font, then runs are joined back into their paragraph/cell.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from .legacy_fonts.font_family_resolver import is_legacy_devanagari_font
from .legacy_fonts.run_decoder import RunDecodeResult, decode_run


@dataclass
class DecodedLine:
    text: str
    page_break_before: bool
    run_results: list[RunDecodeResult] = field(default_factory=list)

    @property
    def min_plausibility(self) -> float:
        if not self.run_results:
            return 1.0
        return min(r.plausibility for r in self.run_results if r.text.strip())


def _iter_block_items(parent):
    """Yield Paragraph/Table objects from a document body in order."""
    if hasattr(parent, "element"):
        parent_elm = parent.element.body
    else:
        parent_elm = parent._element
    for child in parent_elm.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _run_font_name(run) -> str | None:
    rpr = run._element.rPr
    if rpr is None:
        return None
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        return None
    return rfonts.get(qn("w:ascii"))


def _has_page_break_before(paragraph: Paragraph) -> bool:
    for run in paragraph.runs:
        brs = run._element.findall(qn("w:br"))
        for br in brs:
            if br.get(qn("w:type")) == "page":
                return True
    return False


def _group_runs_by_classification(paragraph: Paragraph):
    """Merge consecutive runs that share the same legacy/passthrough
    classification, so word-internal splits (e.g. a matra typed in a
    separate <w:r> from its consonant) don't break kru2uni's
    within-call reordering logic, which only sees one decode() call's
    worth of text at a time.
    """
    groups: list[tuple[str, str | None]] = []  # (concatenated_text, font_name)
    current_text = ""
    current_font: str | None = None
    current_is_legacy: bool | None = None
    for run in paragraph.runs:
        if not run.text:
            continue
        font_name = _run_font_name(run)
        is_legacy = is_legacy_devanagari_font(font_name)
        if current_is_legacy is None or is_legacy == current_is_legacy:
            current_text += run.text
            current_font = current_font or font_name
        else:
            groups.append((current_text, current_font))
            current_text = run.text
            current_font = font_name
        current_is_legacy = is_legacy
    if current_text:
        groups.append((current_text, current_font))
    return groups


def _decode_paragraph(paragraph: Paragraph) -> DecodedLine:
    results = [
        decode_run(raw_text, font_name)
        for raw_text, font_name in _group_runs_by_classification(paragraph)
    ]
    text = "".join(r.text for r in results)
    return DecodedLine(
        text=text,
        page_break_before=_has_page_break_before(paragraph),
        run_results=results,
    )


def load_docx_lines(path: str) -> list[DecodedLine]:
    """Return decoded logical lines (paragraphs, and table cells as lines) in document order."""
    doc = Document(path)
    lines: list[DecodedLine] = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            line = _decode_paragraph(block)
            if line.text.strip() or line.page_break_before:
                lines.append(line)
        elif isinstance(block, Table):
            for row in block.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        line = _decode_paragraph(paragraph)
                        if line.text.strip():
                            lines.append(line)
    return lines
