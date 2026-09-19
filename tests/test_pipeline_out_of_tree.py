import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingestion.pipeline import ingest_file

# scripts/inspect_letter.py is meant to preview any file, including
# one that isn't (yet) filed under data/letters/<department>/ -- e.g.
# a fixture, or a letter you're still deciding where to put. Crashing
# on a path outside data_root defeats that purpose.
FIXTURE_PDF = Path(__file__).parent / "fixtures/ocr/scanned_sample.pdf"
DATA_ROOT = Path("data/letters")


def test_ingest_file_outside_data_root_does_not_crash():
    records = ingest_file(FIXTURE_PDF, DATA_ROOT)
    assert len(records) == 1
    assert records[0].department == "unknown"
    assert records[0].office == "unknown"
    assert "समाहरणालय" in records[0].text
