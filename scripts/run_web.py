#!/usr/bin/env python3
"""Run the local web app (generation UI + admin page).

Usage:
    python scripts/run_web.py

Then open http://127.0.0.1:8000/ (or WEB_HOST:WEB_PORT from .env).
Requires the letters already ingested (python scripts/ingest.py) and,
for real generation, a running Ollama server with the configured
model pulled -- see README. The server starts fine without Ollama;
only POST /api/generate will fail until one is reachable.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._console import ensure_utf8_console

ensure_utf8_console()

import uvicorn

from config.settings import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.web_host, port=settings.web_port, reload=False)
