"""Human-override sidecars layered over auto-extracted metadata.

Convention: <letter_id>.meta.auto.json is written fresh by every
ingestion run (never hand-edited). <letter_id>.meta.json is written
once by a human correcting fields and is never overwritten by
re-running ingestion -- only its *absence* triggers falling back to
the auto version. Merge is field-by-field: a sidecar only needs to
set the fields it's correcting.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_sidecar(sidecar_path: Path) -> dict:
    if not sidecar_path.exists():
        return {}
    with sidecar_path.open(encoding="utf-8") as f:
        return json.load(f)


def write_auto_metadata(auto_path: Path, metadata: dict) -> None:
    auto_path.parent.mkdir(parents=True, exist_ok=True)
    with auto_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def merge_metadata(auto_metadata: dict, sidecar_overrides: dict) -> dict:
    """Sidecar fields take precedence; unset sidecar fields fall back to auto."""
    merged = dict(auto_metadata)
    for key, value in sidecar_overrides.items():
        if value is not None:
            merged[key] = value
    return merged


def resolve_metadata(auto_path: Path, sidecar_path: Path, auto_metadata: dict) -> dict:
    write_auto_metadata(auto_path, auto_metadata)
    overrides = load_sidecar(sidecar_path)
    return merge_metadata(auto_metadata, overrides)
