import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.export.pdf_export import PdfExportUnavailable, render_letter_pdf

SOFFICE_MISSING = shutil.which("soffice") is None and shutil.which("libreoffice") is None
requires_soffice = pytest.mark.skipif(
    SOFFICE_MISSING,
    reason="soffice/libreoffice not installed (see README for libreoffice-writer)",
)

DRAFT = """सारण समाहरणालय, छपरा

विषय: शिक्षकों की कमी के संबंध में।

महोदय,

निवेदन है कि शिक्षकों के पद रिक्त हैं।

भवदीय,
[नाम]"""


@requires_soffice
def test_render_letter_pdf_creates_real_pdf(tmp_path: Path):
    output = render_letter_pdf(
        DRAFT, tmp_path / "letter.pdf",
        font_name="Noto Sans Devanagari", font_size_pt=12,
        margin_cm=2.5, line_spacing=1.5,
    )
    assert output.exists()
    assert output.stat().st_size > 1000
    assert output.read_bytes()[:4] == b"%PDF"


@requires_soffice
def test_render_letter_pdf_text_is_extractable_and_correct(tmp_path: Path):
    import fitz  # PyMuPDF

    output = render_letter_pdf(
        DRAFT, tmp_path / "letter.pdf",
        font_name="Noto Sans Devanagari", font_size_pt=12,
        margin_cm=2.5, line_spacing=1.5,
    )
    doc = fitz.open(str(output))
    text = doc[0].get_text()
    assert "शिक्षकों" in text
    assert "महोदय" in text


@requires_soffice
def test_concurrent_conversions_do_not_interfere(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor

    def job(i: int) -> bool:
        out = render_letter_pdf(
            f"पत्र संख्या {i}\n\nविषय: परीक्षण {i}।",
            tmp_path / f"letter_{i}.pdf",
            font_name="Noto Sans Devanagari", font_size_pt=12,
            margin_cm=2.5, line_spacing=1.5,
        )
        return out.exists() and out.stat().st_size > 500

    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(job, range(3)))
    assert all(results)


def test_pdf_export_unavailable_raises_clear_error(monkeypatch):
    import src.export.pdf_export as pdf_export_module

    monkeypatch.setattr(pdf_export_module.shutil, "which", lambda name: None)
    with pytest.raises(PdfExportUnavailable):
        pdf_export_module._soffice_binary()
