import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingestion.docx_loader import load_docx_lines
from src.ingestion.segmentation import segment_letters

BANKING_CELL_DOCX = "data/letters/district_administration/banking_cell/banking_cell_forwarding_letters.docx"
ESTABLISHMENT_DOCX = "data/letters/district_administration/establishment_branch/disciplinary_order_hridaya_prasad.docx"


def test_multi_letter_file_splits_into_many_segments():
    # Corrects an earlier, wrong "~6 letters" visual estimate of this
    # file -- it actually recurs ~45 times. This is the real,
    # human-confirmed count (by reading the segmentation report), not
    # a guess -- see segmentation.py's module docstring.
    lines = load_docx_lines(BANKING_CELL_DOCX)
    report = segment_letters(lines)
    assert report.gated_as_single_record is False
    assert len(report.segments) >= 40
    # Every segment should have found a विषय line -- if this drops,
    # the anchor/lookback heuristic is probably misaligned.
    with_subject = sum(1 for s in report.segments if s.matched_subject)
    assert with_subject / len(report.segments) > 0.9


def test_single_letter_file_stays_ungated():
    lines = load_docx_lines(ESTABLISHMENT_DOCX)
    report = segment_letters(lines)
    assert report.gated_as_single_record is True
    assert len(report.segments) == 1
    assert report.segments[0].start_line == 0
    assert report.segments[0].end_line == len(lines) - 1


def test_segments_do_not_overlap_and_cover_the_document():
    lines = load_docx_lines(BANKING_CELL_DOCX)
    report = segment_letters(lines)
    prev_end = -1
    for seg in report.segments:
        assert seg.start_line == prev_end + 1
        assert seg.end_line >= seg.start_line
        prev_end = seg.end_line
    assert prev_end == len(lines) - 1


def test_each_segment_contains_its_own_letterhead_not_a_neighbors_signature():
    lines = load_docx_lines(BANKING_CELL_DOCX)
    report = segment_letters(lines)
    for seg in report.segments[1:]:
        first_line = lines[seg.start_line].text.strip()
        assert "समाहरणालय" in first_line or "पत्रांक" in first_line
