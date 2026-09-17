"""Deterministic fakes for model-dependent components, used across
tests so nothing in this test suite needs network/model access."""
from __future__ import annotations

import hashlib

from src.embeddings.base import Embedder


class FakeEmbedder(Embedder):
    """Deterministic pseudo-embedding: hashes text into a fixed-size
    vector. Two identical texts get identical vectors; this is enough
    to test plumbing (storage, filtering, top-k) without asserting
    anything about real semantic ranking quality.
    """

    def __init__(self, model_name: str = "fake-embedder", dim: int = 16):
        self.model_name = model_name
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[: self._dim]]

    def dimension(self) -> int:
        return self._dim


class FakeOllamaChatClient:
    """Records the last request and returns a canned response, so
    generation tests can assert on prompt structure without a live
    Ollama server."""

    def __init__(self, canned_response: str = "यह एक परीक्षण पत्र है।"):
        self.canned_response = canned_response
        self.last_messages: list[dict] | None = None
        self.last_model: str | None = None

    def chat(self, model: str, messages: list[dict], temperature: float = 0.2) -> str:
        self.last_model = model
        self.last_messages = messages
        return self.canned_response
