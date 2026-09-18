"""Shared pytest fixtures for API tests.

The FastAPI routers reference the module-level `settings` singleton
directly (`from config.settings import settings`), which is a frozen
dataclass -- `object.__setattr__` bypasses that immutability
deliberately, and it's safe here because every module that imported
`settings` holds a reference to the SAME object, so mutating its
fields in place (then restoring them) is visible everywhere without
needing to patch each importer separately.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_embedder, get_ollama_client, get_retriever, get_store
from app.main import app
from config.settings import settings
from src.retrieval.hybrid import HybridRetriever
from src.store.chroma_store import ChromaLetterStore
from tests.fakes import FakeEmbedder, FakeOllamaChatClient

SETTINGS_OVERRIDE_FIELDS = ("data_dir", "chroma_dir", "export_tmp_dir")


@pytest.fixture
def api_client(tmp_path: Path):
    data_dir = tmp_path / "data" / "letters"
    chroma_dir = tmp_path / "chroma_db"
    export_dir = tmp_path / "tmp_exports"
    data_dir.mkdir(parents=True)

    originals = {field: getattr(settings, field) for field in SETTINGS_OVERRIDE_FIELDS}
    object.__setattr__(settings, "data_dir", data_dir)
    object.__setattr__(settings, "chroma_dir", chroma_dir)
    object.__setattr__(settings, "export_tmp_dir", export_dir)

    embedder = FakeEmbedder()
    store = ChromaLetterStore(chroma_dir, embedder.model_name, embedder.dimension())
    retriever = HybridRetriever(store, embedder)
    ollama_client = FakeOllamaChatClient()

    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_retriever] = lambda: retriever
    app.dependency_overrides[get_ollama_client] = lambda: ollama_client

    client = TestClient(app)
    client.embedder = embedder
    client.store = store
    client.data_dir = data_dir
    client.ollama_client = ollama_client

    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        for field, value in originals.items():
            object.__setattr__(settings, field, value)
