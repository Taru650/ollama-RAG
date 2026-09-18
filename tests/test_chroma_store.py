import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.store.chroma_store import ChromaLetterStore, EmbeddingModelMismatch
from tests.fakes import FakeEmbedder


def test_add_and_query_roundtrip(tmp_path: Path):
    embedder = FakeEmbedder()
    store = ChromaLetterStore(tmp_path, embedder.model_name, embedder.dimension())

    texts = ["बैंकिंग पत्र", "शिक्षा विभाग पत्र", "राजस्व पत्र"]
    ids = ["a", "b", "c"]
    metadatas = [
        {"department": "district_administration", "letter_type": "forwarding_request"},
        {"department": "education", "letter_type": "general_correspondence"},
        {"department": "revenue", "letter_type": "general_correspondence"},
    ]
    store.add_letters(ids, embedder.embed(texts), texts, metadatas)

    assert store.count() == 3

    hits = store.query(embedder.embed(["बैंकिंग पत्र"])[0], top_k=1)
    assert hits[0]["id"] == "a"


def test_department_filter_restricts_results(tmp_path: Path):
    embedder = FakeEmbedder()
    store = ChromaLetterStore(tmp_path, embedder.model_name, embedder.dimension())
    texts = ["पत्र एक", "पत्र दो", "पत्र तीन"]
    store.add_letters(
        ["a", "b", "c"],
        embedder.embed(texts),
        texts,
        [
            {"department": "education"},
            {"department": "revenue"},
            {"department": "revenue"},
        ],
    )
    hits = store.query(embedder.embed(["पत्र"])[0], top_k=10, where={"department": "revenue"})
    assert {h["id"] for h in hits} == {"b", "c"}


def test_embedding_model_mismatch_raises(tmp_path: Path):
    ChromaLetterStore(tmp_path, "model-a", 16)
    with pytest.raises(EmbeddingModelMismatch):
        ChromaLetterStore(tmp_path, "model-b", 32)


def test_delete_by_ids_removes_only_those_letters(tmp_path: Path):
    embedder = FakeEmbedder()
    store = ChromaLetterStore(tmp_path, embedder.model_name, embedder.dimension())
    texts = ["पत्र एक", "पत्र दो"]
    store.add_letters(["a", "b"], embedder.embed(texts), texts, [{"department": "education"}, {"department": "revenue"}])
    store.delete_by_ids(["a"])
    assert store.count() == 1
    remaining = store.get_by_filter(None)
    assert remaining["ids"] == ["b"]


def test_list_distinct_returns_sorted_unique_values(tmp_path: Path):
    embedder = FakeEmbedder()
    store = ChromaLetterStore(tmp_path, embedder.model_name, embedder.dimension())
    texts = ["पत्र एक", "पत्र दो", "पत्र तीन"]
    store.add_letters(
        ["a", "b", "c"], embedder.embed(texts), texts,
        [{"department": "revenue"}, {"department": "education"}, {"department": "revenue"}],
    )
    assert store.list_distinct("department") == ["education", "revenue"]


def test_list_distinct_on_empty_store_returns_empty(tmp_path: Path):
    embedder = FakeEmbedder()
    store = ChromaLetterStore(tmp_path, embedder.model_name, embedder.dimension())
    assert store.list_distinct("department") == []
