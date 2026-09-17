"""Whitespace/line normalization. Deliberately minimal -- structure
(line breaks between paragraphs, tab-separated label/value pairs like
"विषय :-\t...") is meaningful for metadata extraction and must survive."""
from __future__ import annotations

import re

_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+$", re.MULTILINE)


def clean_line(text: str) -> str:
    text = _TRAILING_SPACE_RE.sub("", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def clean_lines(lines: list[str]) -> list[str]:
    return [clean_line(l) for l in lines if l.strip()]
