#!/usr/bin/env python3
"""Ingest all letters under DATA_DIR into the local vector store.

Usage:
    python scripts/ingest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._console import ensure_utf8_console

ensure_utf8_console()

from config.settings import settings
from src.embeddings.factory import build_embedder
from src.ingestion.indexing import index_records
from src.ingestion.pipeline import ingest_directory
from src.store.vector_store import LocalVectorStore


def main() -> None:
    data_root = Path(settings.data_dir)
    if not data_root.exists():
        print(f"Data directory not found: {data_root}")
        sys.exit(1)

    print(f"Scanning {data_root} ...")
    records = ingest_directory(data_root)
    print(f"Found {len(records)} letters after segmentation.")

    if not records:
        print("Nothing to ingest.")
        return

    low_confidence = [r for r in records if r.low_confidence_fields]
    print(f"{len(low_confidence)} letters have at least one low-confidence "
          f"(unfilled/unmatched) metadata field -- this is expected for "
          f"blank पत्रांक/दिनांक template placeholders, not necessarily an error.")

    needs_review = [r for r in records if r.needs_review]
    if needs_review:
        print(f"{len(needs_review)} letters have low decode/OCR confidence and "
              f"NEED MANUAL REVIEW before you trust them (likely a scanned page "
              f"OCR struggled with, or an unrecognized legacy font):")
        for r in needs_review[:20]:
            print(f"  - {r.letter_id} (min_line_plausibility={r.min_line_plausibility:.2f}) "
                  f"from {r.source_file}")
        if len(needs_review) > 20:
            print(f"  ... and {len(needs_review) - 20} more")
        print("  Check these with: python scripts/inspect_letter.py --file <source_file> --all")

    print(f"Building embedder: backend={settings.embedding_backend} model={settings.embedding_model}")
    embedder = build_embedder(
        backend=settings.embedding_backend,
        model_name=settings.embedding_model,
        ollama_host=settings.ollama_host,
    )
    dimension = embedder.dimension()
    print(f"Embedding dimension: {dimension}")

    store = LocalVectorStore(settings.vector_store_dir, embedder.model_name, dimension)

    print("Computing embeddings (this can take a while on CPU)...")
    index_records(records, store, embedder)
    print(f"Ingested {store.count()} letters into {settings.vector_store_dir}")


if __name__ == "__main__":
    main()
