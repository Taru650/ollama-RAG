"""Render a generated Hindi letter draft into a formatted .docx.

Deliberately does NOT impose a rigid template (पत्र संख्या / सेवा में /
विषय / भवदीय as separate injected fields) on top of the model's own
output. The generation prompt already instructs Qwen3 to produce a
complete, properly-structured letter following the retrieved
references' own format -- re-templating it here would risk duplicating
or fighting whatever structure the model actually produced. This
module's job is purely presentation: correct Devanagari font, margins,
and paragraph spacing, preserving the model's own paragraph breaks.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


def _set_run_font(run, font_name: str, font_size_pt: int) -> None:
    run.font.name = font_name
    run.font.size = Pt(font_size_pt)
    # python-docx only sets w:ascii by default; Devanagari text is
    # rendered via the complex-script (cs) font slot in Word/LibreOffice,
    # so set that explicitly or the CJK/complex-script fallback font
    # (often missing Devanagari glyphs) gets used instead.
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), font_name)
    rfonts.set(qn("w:hAnsi"), font_name)
    rfonts.set(qn("w:cs"), font_name)
    rfonts.set(qn("w:eastAsia"), font_name)


def render_letter_docx(
    draft_text: str,
    output_path: Path,
    *,
    font_name: str,
    font_size_pt: int,
    margin_cm: float,
    line_spacing: float,
) -> Path:
    """Write draft_text into a .docx at output_path, return output_path."""
    doc = Document()
    section = doc.sections[0]
    section.left_margin = Cm(margin_cm)
    section.right_margin = Cm(margin_cm)
    section.top_margin = Cm(margin_cm)
    section.bottom_margin = Cm(margin_cm)

    # Paragraphs are separated by a blank line in the model's output;
    # single newlines within a paragraph become explicit line breaks
    # so e.g. an address block's internal line structure survives.
    blocks = draft_text.strip().split("\n\n")
    for block in blocks:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.line_spacing = line_spacing
        paragraph.paragraph_format.space_after = Pt(font_size_pt)
        lines = block.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                paragraph.add_run().add_break()
            run = paragraph.add_run(line)
            _set_run_font(run, font_name, font_size_pt)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path
