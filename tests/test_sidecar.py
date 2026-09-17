import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metadata.sidecar import merge_metadata, resolve_metadata


def test_merge_prefers_sidecar_but_falls_back_to_auto():
    auto = {"department": "district_administration", "subject": "auto subject", "letter_type": "general_correspondence"}
    override = {"department": "revenue", "subject": None}
    merged = merge_metadata(auto, override)
    assert merged["department"] == "revenue"  # overridden
    assert merged["subject"] == "auto subject"  # None override doesn't clobber
    assert merged["letter_type"] == "general_correspondence"  # untouched field kept


def test_resolve_metadata_writes_auto_and_applies_sidecar(tmp_path: Path):
    auto_path = tmp_path / "letter_001.meta.auto.json"
    sidecar_path = tmp_path / "letter_001.meta.json"
    sidecar_path.write_text('{"department": "education"}', encoding="utf-8")

    resolved = resolve_metadata(auto_path, sidecar_path, {"department": "district_administration", "subject": "x"})

    assert auto_path.exists()
    assert resolved["department"] == "education"
    assert resolved["subject"] == "x"


def test_resolve_metadata_without_sidecar_uses_auto_only(tmp_path: Path):
    auto_path = tmp_path / "letter_002.meta.auto.json"
    sidecar_path = tmp_path / "letter_002.meta.json"  # does not exist

    resolved = resolve_metadata(auto_path, sidecar_path, {"department": "health", "subject": "y"})

    assert resolved == {"department": "health", "subject": "y"}
