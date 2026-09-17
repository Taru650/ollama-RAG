"""Thin HTTP client for Ollama's /api/chat, kept constructor-injectable
so tests can swap in a mocked requests.Session (see requests_mock)."""
from __future__ import annotations

import requests


class OllamaChatClient:
    def __init__(self, host: str, session: requests.Session | None = None):
        self._host = host.rstrip("/")
        self._session = session or requests.Session()

    def chat(self, model: str, messages: list[dict], temperature: float = 0.2) -> str:
        resp = self._session.post(
            f"{self._host}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
