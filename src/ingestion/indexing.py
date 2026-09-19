"""Shared LetterRecord -> vector store indexing logic.

Used by both scripts/ingest.py (CLI) and app/routers/admin.py (web
upload/reindex), so the two entry points can't silently drift into
different metadata-filtering behavior.
"""
from __future__ import annotations

from src.embeddings.base import Embedder
from src.ingestion.pipeline import LetterRecord
from src.store.vector_store import LocalVectorStore


def records_to_store_inputs(records: list[LetterRecord]) -> tuple[list[str], list[str], list[dict]]:
    ids = [r.letter_id for r in records]
    texts = [r.text for r in records]
    metadatas = []
    for r in records:
        # Store metadata values must be str/int/float/bool -- drop
        # non-scalar fields (e.g. copy_to list, field_confidence dict)
        # from the filterable metadata; the full text still carries them.
        meta = {k: v for k, v in r.metadata.items() if isinstance(v, (str, int, float, bool))}
        meta["letter_id"] = r.letter_id
        meta["needs_review"] = r.needs_review
        metadatas.append(meta)
    return ids, texts, metadatas


def index_records(records: list[LetterRecord], store: LocalVectorStore, embedder: Embedder) -> int:
    if not records:
        return 0
    ids, texts, metadatas = records_to_store_inputs(records)
    embeddings = embedder.embed(texts)
    store.add_letters(ids, embeddings, texts, metadatas)
    return len(records)
