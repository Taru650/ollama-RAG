"""OCR for scanned/image-only PDF pages via Tesseract (Hindi + English).

Requires the `tesseract-ocr` binary and its Hindi language data
(`tesseract-ocr-hin` on Debian/Ubuntu) installed on the machine -- this
is a system package, not something pip can provide. See README.

OCR output from Tesseract's Hindi model is already Unicode Devanagari
-- this is a completely different problem from the legacy-font .docx
files (typed text in a glyph-encoded font), so none of the
kru2uni/legacy_fonts machinery applies here. What OCR needs instead is
its own uncertainty signal, since misread characters are the failure
mode (not wrong-encoding-table mojibake) -- Tesseract's own per-word
confidence score serves that purpose.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytesseract
from PIL import Image

TESSERACT_LANG = "hin+eng"
LOW_CONFIDENCE_THRESHOLD = 60.0  # Tesseract confidence is 0-100


@dataclass
class OcrResult:
    text: str
    mean_confidence: float
    low_confidence: bool


def ocr_image(image: Image.Image, lang: str = TESSERACT_LANG) -> OcrResult:
    """Run OCR on a single page image and return text + a confidence signal."""
    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

    words = []
    confidences = []
    for text, conf in zip(data["text"], data["conf"]):
        text = text.strip()
        conf = float(conf)
        if text and conf >= 0:
            words.append(text)
            confidences.append(conf)

    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
    full_text = pytesseract.image_to_string(image, lang=lang).strip()

    return OcrResult(
        text=full_text,
        mean_confidence=mean_conf,
        low_confidence=mean_conf < LOW_CONFIDENCE_THRESHOLD if confidences else True,
    )
