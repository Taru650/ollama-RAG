import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.retrieval.hybrid import HybridRetriever
from src.store.vector_store import LocalVectorStore
from tests.fakes import FakeEmbedder

LETTERS = [
    ("edu-1", "शिक्षकों की कमी के संबंध में जिला शिक्षा पदाधिकारी को पत्र", "education", "forwarding_request"),
    ("edu-2", "विद्यालय भवन मरम्मत के संबंध में पत्र", "education", "general_correspondence"),
    ("rev-1", "भूमि अधिग्रहण के संबंध में राजस्व पदाधिकारी को पत्र", "revenue", "forwarding_request"),
    ("bank-1", "बैंक ऋण योजना समीक्षा के संबंध में पत्र", "district_administration", "forwarding_request"),
]


def _build_store_and_retriever(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    ids = [l[0] for l in LETTERS]
    texts = [l[1] for l in LETTERS]
    metas = [{"department": l[2], "letter_type": l[3]} for l in LETTERS]
    store.add_letters(ids, embedder.embed(texts), texts, metas)
    return HybridRetriever(store, embedder)


def test_department_filter_excludes_other_departments(tmp_path: Path):
    retriever = _build_store_and_retriever(tmp_path)
    results = retriever.retrieve("शिक्षा विभाग पत्र", top_k=5, department="education")
    assert results
    assert all(r.metadata["department"] == "education" for r in results)


def test_no_filter_searches_everything(tmp_path: Path):
    retriever = _build_store_and_retriever(tmp_path)
    results = retriever.retrieve("पत्र", top_k=10)
    assert len(results) == len(LETTERS)


def test_top_k_is_respected(tmp_path: Path):
    retriever = _build_store_and_retriever(tmp_path)
    results = retriever.retrieve("पत्र", top_k=2)
    assert len(results) == 2


def test_exact_text_match_ranks_first_via_bm25(tmp_path: Path):
    retriever = _build_store_and_retriever(tmp_path)
    results = retriever.retrieve("भूमि अधिग्रहण के संबंध में राजस्व पदाधिकारी को पत्र", top_k=1)
    assert results[0].id == "rev-1"


def test_empty_result_when_filter_matches_nothing(tmp_path: Path):
    retriever = _build_store_and_retriever(tmp_path)
    results = retriever.retrieve("पत्र", top_k=5, department="health")
    assert results == []
