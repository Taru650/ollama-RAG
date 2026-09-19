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

# A fixed chars-per-token guess for Devanagari text turned out unreliable
# in practice (this project's own real corpus overflowed an 8192-token
# context even after truncating to a "safely under 2 chars/token" 16,384
# characters -- the true ratio for this script/tokenizer is worse than
# that guess, not knowable in advance without asking the model). So
# instead of guessing a character budget, halve the text and retry on
# Ollama's own "exceeds the context length" error until it fits --
# self-correcting regardless of the real tokenizer behavior.
_MAX_CONTEXT_LENGTH_RETRIES = 10


def _is_context_length_error(response_text: str) -> bool:
    return "exceeds the context length" in response_text


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
        self._session = session or requests.Session()
        self._dimension: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for i, text in enumerate(texts):
            original_len = len(text)
            attempt = 0
            while True:
                resp = self._session.post(
                    f"{self._host}/api/embeddings",
                    json={
                        "model": self.model_name,
                        "prompt": text,
                        "options": {"num_ctx": self._num_ctx},
                    },
                    timeout=_REQUEST_TIMEOUT_SECONDS,
                )
                if resp.ok:
                    break
                if _is_context_length_error(resp.text) and attempt < _MAX_CONTEXT_LENGTH_RETRIES:
                    # Halve and retry rather than guess a char budget --
                    # not silent: this is a real loss of content for
                    # this letter's embedding, so it's printed, the
                    # same way needs_review flags are.
                    attempt += 1
                    text = text[: len(text) // 2]
                    continue
                # raise_for_status() alone throws away Ollama's response
                # body, which is where the actual reason lives (e.g. a
                # JSON {"error": "..."} explaining *why* the model
                # rejected this input) -- surface it instead of leaving
                # a bare "500 Internal Server Error" to debug blind.
                raise RuntimeError(
                    f"Ollama embeddings request failed (HTTP {resp.status_code}) on "
                    f"text {i + 1}/{len(texts)} ({len(text)} chars, "
                    f"{original_len} before any truncation): {resp.text[:1000]!r}"
                )
            if len(text) < original_len:
                print(
                    f"WARNING: text {i + 1}/{len(texts)} was truncated from "
                    f"{original_len} to {len(text)} chars to fit Ollama's context "
                    f"window (num_ctx={self._num_ctx}) for embedding only (the "
                    f"stored/displayed text is unaffected). Consider raising "
                    f"EMBEDDING_NUM_CTX in .env if this happens often.",
                    file=sys.stderr,
                )
            vector = resp.json()["embedding"]
            vectors.append(vector)
        return vectors

    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = len(self.embed(["dimension probe"])[0])
        return self._dimension
