#!/usr/bin/env python3
"""Print the decoded text of one or all letters for manual QA.

This is the "manual gate" step the README's handoff checklist calls
for: after running ingest.py, a human needs to actually read the
converted Devanagari and confirm it isn't garbled before trusting the
pipeline on the rest of the corpus.

Usage:
    python scripts/inspect_letter.py --file path/to/letter.docx
    python scripts/inspect_letter.py --file path/to/letter.docx --id banking_cell_forwarding_letters__seg003
    python scripts/inspect_letter.py --file path/to/letter.docx --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from src.ingestion.pipeline import ingest_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to a .docx/.txt letter file")
    parser.add_argument("--id", help="Only show this specific letter_id")
    parser.add_argument("--all", action="store_true", help="Show every segment in the file")
    args = parser.parse_args()

    file_path = Path(args.file)
    data_root = Path(settings.data_dir)
    records = ingest_file(file_path, data_root)

    print(f"{len(records)} letter(s) found in {file_path}\n")

    for r in records:
        if args.id and r.letter_id != args.id:
            continue
        if not args.id and not args.all and r.segment_index > 0:
            continue
        print("=" * 70)
        print(f"id: {r.letter_id}")
        print(f"department/office: {r.department}/{r.office}")
        print(f"letter_type: {r.metadata.get('letter_type')}")
        print(f"subject: {r.metadata.get('subject')}")
        print(f"reference: {r.metadata.get('reference_number')} / {r.metadata.get('reference_date')}")
        if r.low_confidence_fields:
            print(f"low-confidence fields: {r.low_confidence_fields}")
        print("-" * 70)
        print(r.text)
        print()

    if not args.all and not args.id and len(records) > 1:
        print(f"(showing only the first segment; pass --all to see all {len(records)}, "
              f"or --id <letter_id> for one specific segment)")


if __name__ == "__main__":
    main()
