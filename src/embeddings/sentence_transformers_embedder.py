"""Embeddings via a local sentence-transformers model (CPU-only).

Lazy-loaded so importing this module doesn't require the (heavy,
torch-backed) sentence-transformers package or a downloaded model
unless this backend is actually selected.
"""
from __future__ import annotations

from .base import Embedder


class SentenceTransformersEmbedder(Embedder):
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def dimension(self) -> int:
        return self._load().get_sentence_embedding_dimension()
