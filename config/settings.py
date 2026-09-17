"""Central configuration, loaded from environment variables / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    ollama_host: str = _env("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = _env("OLLAMA_MODEL", "qwen3:1.7b")

    embedding_backend: str = _env("EMBEDDING_BACKEND", "sentence_transformers")
    embedding_model: str = _env("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

    top_k: int = int(_env("TOP_K", "5"))

    chroma_dir: Path = Path(_env("CHROMA_DIR", "./chroma_db"))
    data_dir: Path = Path(_env("DATA_DIR", "./data/letters"))

    generation_temperature: float = float(_env("GENERATION_TEMPERATURE", "0.2"))


settings = Settings()
