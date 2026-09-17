"""Embedder interface -- swappable via config, never hardcoded."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Embedder(ABC):
    model_name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, same order."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension for this model."""
