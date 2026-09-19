import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingestion.docx_loader import load_docx_lines
from src.ingestion.segmentation import segment_letters
from src.metadata.extractors import extract_metadata


def _segment_text_lines(path, index=0):
    lines = load_docx_lines(path)
    report = segment_letters(lines)
    seg = report.segments[index]
    return [l.text for l in lines[seg.start_line:seg.end_line + 1]]


def test_subject_extracted_from_banking_cell_letter():
    text_lines = _segment_text_lines(
        "data/letters/district_administration/banking_cell/banking_cell_forwarding_letters.docx"
    )
    meta = extract_metadata(text_lines)
    assert meta.subject is not None
    assert "अग्रसारित" in meta.subject
    assert meta.letter_type == "forwarding_request"


def test_context_reference_number_and_date_parsed_when_present():
    text_lines = _segment_text_lines(
        "data/letters/district_administration/banking_cell/banking_cell_forwarding_letters.docx"
    )
    meta = extract_metadata(text_lines)
    assert meta.reference_number == "75"
    assert meta.reference_date == "23.03.2023"


def test_blank_placeholder_reference_is_none_not_dashes():
    # Second letter in the file has no प्रसंग line -- its own पत्रांक
    # placeholder must come back as None, never the literal dashes.
    text_lines = _segment_text_lines(
        "data/letters/district_administration/banking_cell/banking_cell_forwarding_letters.docx",
        index=1,
    )
    meta = extract_metadata(text_lines)
    assert meta.reference_number is None
    assert meta.reference_date is None
    assert meta.field_confidence.get("reference_number") is False


def test_recipient_and_sender_designation_extracted():
    text_lines = _segment_text_lines(
        "data/letters/district_administration/banking_cell/banking_cell_forwarding_letters.docx"
    )
    meta = extract_metadata(text_lines)
    assert "प्रबंधक" in meta.recipient_designation
    assert "प्रभारी पदाधिकारी" in meta.sender_designation


def test_disciplinary_order_classified_correctly():
    text_lines = _segment_text_lines(
        "data/letters/district_administration/establishment_branch/disciplinary_order_hridaya_prasad.docx"
    )
    meta = extract_metadata(text_lines)
    assert meta.letter_type == "disciplinary_order"
