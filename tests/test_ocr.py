import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from PIL import Image

from src.ingestion.ocr import ocr_image
from src.ingestion.pdf_loader import load_pdf_lines

TESSERACT_MISSING = shutil.which("tesseract") is None
requires_tesseract = pytest.mark.skipif(
    TESSERACT_MISSING,
    reason="tesseract-ocr not installed (see README for system package install)",
)

FIXTURE_PNG = os.path.join(os.path.dirname(__file__), "fixtures/ocr/hindi_sample.png")
FIXTURE_PDF = os.path.join(os.path.dirname(__file__), "fixtures/ocr/scanned_sample.pdf")
EXPECTED_TEXT = "सारण समाहरणालय, छपरा"


@requires_tesseract
def test_ocr_image_reads_hindi_text_correctly():
    image = Image.open(FIXTURE_PNG)
    result = ocr_image(image)
    assert result.text.strip() == EXPECTED_TEXT
    assert result.mean_confidence > 70
    assert result.low_confidence is False


@requires_tesseract
def test_scanned_pdf_falls_back_to_ocr():
    lines = load_pdf_lines(FIXTURE_PDF)
    assert len(lines) == 1
    assert lines[0].text.strip() == EXPECTED_TEXT
    assert lines[0].page_break_before is True
    assert lines[0].min_plausibility > 0.7


def test_ocr_module_requires_tesseract_binary_present_message():
    # Sanity check the skip marker itself works as intended locally --
    # not a real assertion about OCR behavior.
    if TESSERACT_MISSING:
        pytest.skip("tesseract not installed -- expected skip path exercised")
    assert shutil.which("tesseract") is not None
