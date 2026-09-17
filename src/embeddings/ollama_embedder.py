"""Embeddings via a local Ollama server's /api/embeddings endpoint.

Availability of a given embedding model (e.g. qwen3-embedding:0.6b) on
Ollama is unverified from the build environment -- verify locally with
``ollama pull <model>`` before relying on this backend; fall back to
the sentence_transformers backend otherwise (see config/settings.py).
"""
from __future__ import annotations

import requests

from .base import Embedder


class OllamaEmbedder(Embedder):
    def __init__(self, model_name: str, host: str, session: requests.Session | None = None):
        self.model_name = model_name
        self._host = host.rstrip("/")
        self._session = session or requests.Session()
        self._dimension: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            resp = self._session.post(
                f"{self._host}/api/embeddings",
                json={"model": self.model_name, "prompt": text},
                timeout=120,
            )
            resp.raise_for_status()
            vector = resp.json()["embedding"]
            vectors.append(vector)
        return vectors

    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = len(self.embed(["dimension probe"])[0])
        return self._dimension
