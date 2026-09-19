import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.retrieval.department_detector import detect_department
from src.retrieval.hybrid import HybridRetriever
from src.store.vector_store import LocalVectorStore
from tests.fakes import FakeEmbedder

LETTERS = [
    ("edu-1", "शिक्षकों की कमी के संबंध में जिला शिक्षा पदाधिकारी को पत्र", "education", "forwarding_request"),
    ("edu-2", "विद्यालय भवन मरम्मत एवं शिक्षक नियुक्ति के संबंध में पत्र", "education", "general_correspondence"),
    ("edu-3", "छात्रवृत्ति योजना के संबंध में शिक्षा विभाग को पत्र", "education", "general_correspondence"),
    ("rev-1", "भूमि अधिग्रहण के संबंध में राजस्व पदाधिकारी को पत्र", "revenue", "forwarding_request"),
    ("rev-2", "खाता संख्या एवं दाखिल खारिज के संबंध में राजस्व पत्र", "revenue", "general_correspondence"),
    ("rev-3", "भूमि विवाद एवं खाता संख्या सुधार के संबंध में राजस्व पदाधिकारी को पत्र", "revenue", "general_correspondence"),
    ("bank-1", "बैंक ऋण योजना समीक्षा के संबंध में पत्र", "district_administration", "forwarding_request"),
]


def _build_retriever(tmp_path: Path) -> HybridRetriever:
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    ids = [l[0] for l in LETTERS]
    texts = [l[1] for l in LETTERS]
    metas = [{"department": l[2], "letter_type": l[3]} for l in LETTERS]
    store.add_letters(ids, embedder.embed(texts), texts, metas)
    return HybridRetriever(store, embedder)


def test_detects_dominant_department_from_query_text(tmp_path: Path):
    retriever = _build_retriever(tmp_path)
    detected = detect_department("शिक्षकों की कमी एवं शिक्षक नियुक्ति के संबंध में पत्र तैयार करें", retriever)
    assert detected == "education"


def test_detects_revenue_department(tmp_path: Path):
    retriever = _build_retriever(tmp_path)
    detected = detect_department("भूमि अधिग्रहण एवं खाता संख्या दाखिल खारिज के संबंध में पत्र", retriever)
    assert detected == "revenue"


def test_ambiguous_query_returns_none(tmp_path: Path):
    retriever = _build_retriever(tmp_path)
    # A generic phrase with no department-specific vocabulary shouldn't
    # force a confident pick.
    detected = detect_department("पत्र तैयार करें", retriever, top_k=6, min_vote_fraction=0.99)
    assert detected is None


def test_no_letters_in_store_returns_none(tmp_path: Path):
    embedder = FakeEmbedder()
    store = LocalVectorStore(tmp_path, embedder.model_name, embedder.dimension())
    retriever = HybridRetriever(store, embedder)
    assert detect_department("कोई भी अनुरोध", retriever) is None
