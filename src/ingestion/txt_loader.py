"""Plain .txt loader. Assumed to already be Unicode -- no legacy font
conversion applies (that problem is specific to old .docx files typed
in glyph-encoded fonts, not plain text files)."""
from __future__ import annotations

from pathlib import Path


def load_txt_lines(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]
