import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingestion.docx_loader import load_docx_lines
from src.ingestion.legacy_fonts.font_family_resolver import is_legacy_devanagari_font
from src.ingestion.legacy_fonts.kru2uni import kru2uni
from src.ingestion.legacy_fonts.plausibility_scorer import plausibility_score
from tests.fixtures.legacy_fonts.golden_pairs import GOLDEN_PAIRS

REAL_DOCX_PATHS = [
    "data/letters/district_administration/banking_cell/banking_cell_forwarding_letters.docx",
    "data/letters/district_administration/establishment_branch/disciplinary_order_hridaya_prasad.docx",
]


def test_golden_pairs_decode_exactly():
    for raw, expected in GOLDEN_PAIRS:
        assert kru2uni(raw) == expected


def test_font_family_resolver():
    assert is_legacy_devanagari_font("DevLys 040") is True
    assert is_legacy_devanagari_font("Kruti Dev 041") is True
    assert is_legacy_devanagari_font("Kruti Dev 500") is True
    assert is_legacy_devanagari_font("Times New Roman") is False
    assert is_legacy_devanagari_font("Mangal") is False
    assert is_legacy_devanagari_font("Calibri") is False
    assert is_legacy_devanagari_font(None) is False


def test_plausibility_score_of_converted_text_is_high():
    for _, expected in GOLDEN_PAIRS:
        assert plausibility_score(expected) > 0.8


def test_plausibility_score_flags_malformed_combining_marks():
    # Real artifacts pulled from the sample corpus: a stray leading
    # "z" (-> ्) before "विश्वासभाजन", and anusvara-only table-header
    # padding -- both start with a combining mark with no base
    # character, which is the actual, checkable signature of
    # malformed Devanagari (unlike raw Devanagari-block ratio, which
    # both of these already max out on).
    malformed = "्रविष्वासभाजन"
    clean = "विश्वासभाजन"
    assert plausibility_score(clean) > plausibility_score(malformed)
    assert plausibility_score("ंंंं") < 0.5


def test_real_docx_files_mostly_decode_cleanly():
    # Not asserting zero low-plausibility lines: the real corpus has a
    # handful of genuine source-document typing artifacts (e.g. a
    # stray table-header "aaaaaaaaa" padding, a stray leading "z"
    # before one "विश्वासभाजन" closing) that decode to genuinely
    # malformed Devanagari because the ORIGINAL typist made a typo --
    # not because the converter is wrong. The plausibility scorer is
    # designed to surface exactly these for human audit (see
    # scripts/inspect_letter.py), not to silently hide or "fix" them.
    # This test guards against a *regression* (a real bug suddenly
    # flooding many more lines with low scores), not against the
    # known, small, pre-existing set.
    for path in REAL_DOCX_PATHS:
        lines = load_docx_lines(path)
        assert len(lines) > 0
        low_plausibility = [
            line for line in lines
            if line.text.strip() and line.min_plausibility < 0.5
        ]
        assert len(low_plausibility) <= 10, (
            f"{path}: unexpectedly many low-plausibility decoded lines "
            f"({len(low_plausibility)}): "
            f"{[l.text[:60] for l in low_plausibility]}"
        )


def test_real_docx_letterhead_decodes_correctly():
    lines = load_docx_lines(REAL_DOCX_PATHS[0])
    texts = [l.text for l in lines]
    assert "सारण समाहरणालय, छपरा" in texts[:3]


def test_real_docx_english_letterhead_not_mangled():
    lines = load_docx_lines(REAL_DOCX_PATHS[1])
    texts = " ".join(l.text for l in lines)
    assert "Vaibhava Srivastava" in texts
    assert "dm-saran.bih@nic.in" in texts


def test_split_run_word_reorders_matra_correctly():
    # Regression test for the run-grouping bug: "f" (i-matra) and its
    # consonant run "tyk" must decode together as "जिला", not
    # separately as "ि" + "जला" -> "िजला" (malformed Unicode order).
    from src.ingestion.legacy_fonts.run_decoder import decode_run

    combined_raw = "f" + "tyk"
    result = decode_run(combined_raw, "DevLys 040")
    assert result.text == "जिला"
