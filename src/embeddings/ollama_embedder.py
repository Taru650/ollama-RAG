"""Embeddings via a local Ollama server's /api/embeddings endpoint.

Availability of a given embedding model (e.g. qwen3-embedding:0.6b) on
Ollama is now confirmed working end-to-end, including on a real
CPU-only Windows machine (this project's target hardware profile) --
see config/settings.py for the "ollama" vs "sentence_transformers"
backend choice.
"""
from __future__ import annotations

import sys

import requests

from .base import Embedder

# The first call after the Ollama server starts (or after its
# keep_alive window expires) has to load the model from disk into
# RAM before it can respond -- on an 8GB CPU-only machine this project
# targets, that cold load plus per-token compute can genuinely exceed
# a minute. A short timeout here doesn't make ingestion faster, it
# just turns a slow-but-working call into a crash.
_REQUEST_TIMEOUT_SECONDS = 300

# Conservative, deliberately pessimistic chars-per-token estimate for
# Devanagari text so the truncation safety net below stays inside
# whatever num_ctx Ollama is actually given, even if the real tokenizer
# does better than this. Only used to pick a truncation length -- never
# assumed accurate enough to skip asking Ollama and just trust it.
_CHARS_PER_TOKEN_ESTIMATE = 2


class OllamaEmbedder(Embedder):
    def __init__(
        self,
        model_name: str,
        host: str,
        num_ctx: int = 8192,
        session: requests.Session | None = None,
    ):
        self.model_name = model_name
        self._host = host.rstrip("/")
        self._num_ctx = num_ctx
        self._max_chars = num_ctx * _CHARS_PER_TOKEN_ESTIMATE
        self._session = session or requests.Session()
        self._dimension: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for i, text in enumerate(texts):
            if len(text) > self._max_chars:
                # A letter this long will exceed num_ctx regardless of
                # the real tokenizer ratio -- truncate rather than let
                # one oversized letter crash ingestion for every other
                # letter in the batch. Not silent: this is a real loss
                # of content for that one letter's embedding, so it's
                # printed, the same way needs_review flags are.
                print(
                    f"WARNING: text {i + 1}/{len(texts)} is {len(text)} chars, "
                    f"longer than this embedder's ~{self._max_chars}-char safety "
                    f"limit (num_ctx={self._num_ctx}) -- truncating for embedding "
                    f"only (the stored/displayed text is unaffected). Consider "
                    f"raising EMBEDDING_NUM_CTX in .env if this happens often.",
                    file=sys.stderr,
                )
                text = text[: self._max_chars]
            resp = self._session.post(
                f"{self._host}/api/embeddings",
                json={
                    "model": self.model_name,
                    "prompt": text,
                    "options": {"num_ctx": self._num_ctx},
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            if not resp.ok:
                # raise_for_status() alone throws away Ollama's response
                # body, which is where the actual reason lives (e.g. a
                # JSON {"error": "..."} explaining *why* the model
                # rejected this input) -- surface it instead of leaving
                # a bare "500 Internal Server Error" to debug blind.
                raise RuntimeError(
                    f"Ollama embeddings request failed (HTTP {resp.status_code}) on "
                    f"text {i + 1}/{len(texts)} ({len(text)} chars): {resp.text[:1000]!r}"
                )
            vector = resp.json()["embedding"]
            vectors.append(vector)
        return vectors

    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = len(self.embed(["dimension probe"])[0])
        return self._dimension
