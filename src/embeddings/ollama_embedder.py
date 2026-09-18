"""Embeddings via a local Ollama server's /api/embeddings endpoint.

Availability of a given embedding model (e.g. qwen3-embedding:0.6b) on
Ollama is now confirmed working end-to-end, including on a real
CPU-only Windows machine (this project's target hardware profile) --
see config/settings.py for the "ollama" vs "sentence_transformers"
backend choice.
"""
from __future__ import annotations

import requests

from .base import Embedder

# The first call after the Ollama server starts (or after its
# keep_alive window expires) has to load the model from disk into
# RAM before it can respond -- on an 8GB CPU-only machine this project
# targets, that cold load plus per-token compute can genuinely exceed
# a minute. A short timeout here doesn't make ingestion faster, it
# just turns a slow-but-working call into a crash.
_REQUEST_TIMEOUT_SECONDS = 300


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
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            vector = resp.json()["embedding"]
            vectors.append(vector)
        return vectors

    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = len(self.embed(["dimension probe"])[0])
        return self._dimension
