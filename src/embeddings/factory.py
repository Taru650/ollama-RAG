"""Pick an Embedder implementation from config -- the only place that
needs to know both backend classes exist."""
from __future__ import annotations

from .base import Embedder


def build_embedder(backend: str, model_name: str, ollama_host: str = "") -> Embedder:
    if backend == "ollama":
        from .ollama_embedder import OllamaEmbedder

        return OllamaEmbedder(model_name=model_name, host=ollama_host)
    if backend == "sentence_transformers":
        from .sentence_transformers_embedder import SentenceTransformersEmbedder

        return SentenceTransformersEmbedder(model_name=model_name)
    raise ValueError(f"Unknown EMBEDDING_BACKEND: {backend!r} (expected 'ollama' or 'sentence_transformers')")
