"""Safe identifiers for source files, used in admin API URLs.

A raw relative path in a URL path segment is asking for trouble
(encoding issues, and more importantly path traversal if a delete
endpoint trusted it directly) -- so admin endpoints identify a source
file by a base64-urlsafe encoding of its path relative to DATA_DIR,
and decode_doc_id re-validates the result stays inside DATA_DIR before
any filesystem operation touches it.
"""
from __future__ import annotations

import base64
from pathlib import Path


class InvalidDocumentId(ValueError):
    pass


def encode_doc_id(file_path: Path, data_root: Path) -> str:
    rel = file_path.resolve().relative_to(data_root.resolve())
    return base64.urlsafe_b64encode(str(rel).encode("utf-8")).decode("ascii")


def decode_doc_id(doc_id: str, data_root: Path) -> Path:
    try:
        rel = base64.urlsafe_b64decode(doc_id.encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise InvalidDocumentId(f"Malformed document id: {doc_id!r}") from exc

    resolved_root = data_root.resolve()
    candidate = (resolved_root / rel).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise InvalidDocumentId(f"Document id resolves outside DATA_DIR: {doc_id!r}")
    return candidate
