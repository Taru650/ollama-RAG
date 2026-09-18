import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.store.vector_store import EmbeddingModelMismatch, LocalVectorStore
from tests.fakes import FakeEmbedder


def test_add_and_query_roundtrip(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())

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
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
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
    LocalVectorStore(tmp_path, "model-a", 16)
    with pytest.raises(EmbeddingModelMismatch):
        LocalVectorStore(tmp_path, "model-b", 32)


def test_delete_by_ids_removes_only_those_letters(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    texts = ["पत्र एक", "पत्र दो"]
    store.add_letters(["a", "b"], embedder.embed(texts), texts, [{"department": "education"}, {"department": "revenue"}])
    store.delete_by_ids(["a"])
    assert store.count() == 1
    remaining = store.get_by_filter(None)
    assert remaining["ids"] == ["b"]


def test_list_distinct_returns_sorted_unique_values(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    texts = ["पत्र एक", "पत्र दो", "पत्र तीन"]
    store.add_letters(
        ["a", "b", "c"], embedder.embed(texts), texts,
        [{"department": "revenue"}, {"department": "education"}, {"department": "revenue"}],
    )
    assert store.list_distinct("department") == ["education", "revenue"]


def test_list_distinct_on_empty_store_returns_empty(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    assert store.list_distinct("department") == []


def test_add_letters_upserts_existing_id(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    store.add_letters(["a"], embedder.embed(["पहला पाठ"]), ["पहला पाठ"], [{"department": "education"}])
    store.add_letters(["a"], embedder.embed(["नया पाठ"]), ["नया पाठ"], [{"department": "revenue"}])
    assert store.count() == 1
    result = store.get_by_ids(["a"])
    assert result["documents"] == ["नया पाठ"]
    assert result["metadatas"][0]["department"] == "revenue"


def test_persists_and_reloads_from_disk(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    texts = ["पहला पत्र", "दूसरा पत्र"]
    store.add_letters(["a", "b"], embedder.embed(texts), texts, [{"department": "education"}, {"department": "revenue"}])

    reloaded = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    assert reloaded.count() == 2
    assert reloaded.get_by_ids(["a"])["documents"] == ["पहला पत्र"]
    hits = reloaded.query(embedder.embed(["पहला पत्र"])[0], top_k=1)
    assert hits[0]["id"] == "a"


def test_delete_by_filter_removes_matching_letters(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    texts = ["पत्र एक", "पत्र दो", "पत्र तीन"]
    store.add_letters(
        ["a", "b", "c"], embedder.embed(texts), texts,
        [{"source_file": "x.docx"}, {"source_file": "x.docx"}, {"source_file": "y.docx"}],
    )
    store.delete_by_filter({"source_file": "x.docx"})
    assert store.count() == 1
    assert store.get_by_filter(None)["ids"] == ["c"]
