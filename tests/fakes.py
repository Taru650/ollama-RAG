"""Deterministic fakes for model-dependent components, used across
tests so nothing in this test suite needs network/model access."""
from __future__ import annotations

import hashlib
import math
import re

from src.embeddings.base import Embedder

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class FakeEmbedder(Embedder):
    """Deterministic pseudo-embedding using the feature-hashing trick:
    each token hashes to a dimension and accumulates into the vector,
    then it's L2-normalized. Unlike hashing the whole string, this
    means two texts sharing vocabulary get non-trivial cosine
    similarity -- a much closer (if crude) stand-in for how a real
    embedding model behaves than a pure per-string hash, which is
    pure noise with respect to word overlap and silently makes any
    test relying on the semantic half of hybrid retrieval (e.g.
    department detection with no metadata filter to fall back on)
    pass or fail for the wrong reason.
    """

    def __init__(self, model_name: str = "fake-embedder", dim: int = 64):
        self.model_name = model_name
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]

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
