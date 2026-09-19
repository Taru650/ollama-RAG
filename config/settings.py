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

    embedding_backend: str = _env("EMBEDDING_BACKEND", "ollama")
    embedding_model: str = _env("EMBEDDING_MODEL", "qwen3-embedding:0.6b")
    # Ollama backend only: Ollama defaults new requests to a 2048-token
    # context regardless of what the underlying model actually
    # supports, which a single long real-world letter can exceed (a
    # 43k-character disciplinary order in this project's own corpus
    # hit "the input length exceeds the context length" at the
    # default). qwen3-embedding:0.6b supports much larger contexts, so
    # this asks Ollama to use more of it; see also
    # src/embeddings/ollama_embedder.py's truncation safety net for
    # when even this isn't enough.
    embedding_num_ctx: int = int(_env("EMBEDDING_NUM_CTX", "8192"))

    top_k: int = int(_env("TOP_K", "5"))

    vector_store_dir: Path = Path(_env("VECTOR_STORE_DIR", "./vector_store"))
    data_dir: Path = Path(_env("DATA_DIR", "./data/letters"))

    generation_temperature: float = float(_env("GENERATION_TEMPERATURE", "0.2"))
    # Full letter generation is autoregressive (token-by-token), unlike
    # a single-pass embedding call, and the prompt includes retrieved
    # reference letters on top of the request itself -- on an 8GB
    # CPU-only machine (this project's target hardware) this hit
    # Ollama's default 300s client timeout during real end-to-end
    # testing. Raise this in .env if generation still times out.
    generation_timeout_seconds: int = int(_env("GENERATION_TIMEOUT_SECONDS", "600"))

    # Export (DOCX/PDF) -- Noto Sans Devanagari is free/open-source and
    # was the font this project's PDF export was actually verified
    # against (see src/export/); "Nirmala UI" (Windows) or "Mangal"
    # are common alternatives if already installed on your machine.
    docx_font_name: str = _env("DOCX_FONT_NAME", "Noto Sans Devanagari")
    docx_font_size_pt: int = int(_env("DOCX_FONT_SIZE_PT", "12"))
    docx_margin_cm: float = float(_env("DOCX_MARGIN_CM", "2.5"))
    docx_line_spacing: float = float(_env("DOCX_LINE_SPACING", "1.5"))
    export_tmp_dir: Path = Path(_env("EXPORT_TMP_DIR", "./tmp_exports"))

    # Web app
    web_host: str = _env("WEB_HOST", "127.0.0.1")
    web_port: int = int(_env("WEB_PORT", "8000"))


settings = Settings()
