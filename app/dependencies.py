"""Shared singletons for the FastAPI app.

Mirrors the wiring in scripts/generate.py and scripts/ingest.py so the
web app and the CLI scripts stay in sync rather than drifting into two
separate implementations. Cached with lru_cache so the (potentially
slow-to-load, e.g. sentence-transformers) embedder is only constructed
once per process, not per request.

Tests override these with FastAPI's app.dependency_overrides (see
tests/test_api.py) to inject fakes -- no live Ollama server or real
embedding model needed to test the API layer, same posture as the
rest of this project's test suite.
"""
from __future__ import annotations

from functools import lru_cache

from config.settings import settings
from src.embeddings.base import Embedder
from src.embeddings.factory import build_embedder
from src.generation.ollama_client import OllamaChatClient
from src.retrieval.hybrid import HybridRetriever
from src.store.vector_store import LocalVectorStore


@lru_cache
def get_embedder() -> Embedder:
    return build_embedder(
        backend=settings.embedding_backend,
        model_name=settings.embedding_model,
        ollama_host=settings.ollama_host,
    )


@lru_cache
def get_store() -> LocalVectorStore:
    embedder = get_embedder()
    return LocalVectorStore(settings.vector_store_dir, embedder.model_name, embedder.dimension())


@lru_cache
def get_retriever() -> HybridRetriever:
    return HybridRetriever(get_store(), get_embedder())


@lru_cache
def get_ollama_client() -> OllamaChatClient:
    return OllamaChatClient(host=settings.ollama_host)


def reset_caches() -> None:
    """Used by tests and by the admin re-embed action after a config change."""
    get_embedder.cache_clear()
    get_store.cache_clear()
    get_retriever.cache_clear()
    get_ollama_client.cache_clear()
