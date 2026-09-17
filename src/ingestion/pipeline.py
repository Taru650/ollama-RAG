"""Ingestion orchestration: walk data/letters/<department>/<office>/*,
decode, segment into individual letters, extract metadata, and yield
one LetterRecord per logical letter -- ready to embed and store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.metadata.extractors import extract_metadata
from src.metadata.sidecar import resolve_metadata

from .cleaning import clean_lines
from .docx_loader import load_docx_lines
from .pdf_loader import load_pdf_lines
from .segmentation import segment_letters
from .txt_loader import load_txt_lines

SUPPORTED_DOCX = (".docx",)
SUPPORTED_PDF = (".pdf",)
SUPPORTED_TXT = (".txt",)

# Below this, a segment is flagged for human review -- mirrors the
# per-run plausibility score for legacy-font docx text, and Tesseract's
# own confidence for OCR'd scanned pages (see ocr.py / pdf_loader.py).
MIN_TRUSTED_PLAUSIBILITY = 0.6


@dataclass
class LetterRecord:
    letter_id: str
    department: str
    office: str
    source_file: str
    segment_index: int
    text: str
    metadata: dict = field(default_factory=dict)
    low_confidence_fields: list[str] = field(default_factory=list)
    min_line_plausibility: float = 1.0
    needs_review: bool = False


def _department_and_office_from_path(file_path: Path, data_root: Path) -> tuple[str, str]:
    try:
        rel = file_path.resolve().relative_to(data_root.resolve())
    except ValueError:
        # file_path isn't under data_root -- e.g. inspect_letter.py run
        # directly against an arbitrary file (a test fixture, or a
        # letter not yet filed into data/letters/<department>/). Don't
        # crash a QA tool over a path that's outside its own convention.
        return "unknown", "unknown"
    parts = rel.parts
    department = parts[0] if len(parts) > 0 else "unknown"
    office = parts[1] if len(parts) > 2 else "unknown"
    return department, office


def _letter_id(file_path: Path, segment_index: int) -> str:
    stem = file_path.stem
    return f"{stem}__seg{segment_index:03d}"


def _metadata_paths(file_path: Path, segment_index: int) -> tuple[Path, Path]:
    letter_id = _letter_id(file_path, segment_index)
    meta_dir = file_path.parent / ".meta"
    return meta_dir / f"{letter_id}.meta.auto.json", meta_dir / f"{letter_id}.meta.json"


def _records_from_decoded_lines(decoded_lines, file_path: Path, data_root: Path) -> list[LetterRecord]:
    report = segment_letters(decoded_lines)
    department, office = _department_and_office_from_path(file_path, data_root)

    records = []
    for seg_index, segment in enumerate(report.segments):
        segment_lines = decoded_lines[segment.start_line:segment.end_line + 1]
        raw_text_lines = [l.text for l in segment_lines]
        text_lines = clean_lines(raw_text_lines)
        meta = extract_metadata(text_lines)

        auto_meta = {
            "department": department,
            "office": office,
            "source_file": str(file_path),
            **meta.to_dict(),
        }
        auto_path, sidecar_path = _metadata_paths(file_path, seg_index)
        resolved = resolve_metadata(auto_path, sidecar_path, auto_meta)

        low_confidence = [f for f, ok in meta.field_confidence.items() if not ok]
        min_plausibility = min((l.min_plausibility for l in segment_lines if l.text.strip()), default=1.0)

        records.append(LetterRecord(
            letter_id=_letter_id(file_path, seg_index),
            department=resolved.get("department", department),
            office=resolved.get("office", office),
            source_file=str(file_path),
            segment_index=seg_index,
            text="\n".join(text_lines),
            metadata=resolved,
            low_confidence_fields=low_confidence,
            min_line_plausibility=min_plausibility,
            needs_review=min_plausibility < MIN_TRUSTED_PLAUSIBILITY,
        ))
    return records


def ingest_file(file_path: Path, data_root: Path) -> list[LetterRecord]:
    suffix = file_path.suffix.lower()
    if suffix in SUPPORTED_DOCX:
        decoded_lines = load_docx_lines(str(file_path))
        return _records_from_decoded_lines(decoded_lines, file_path, data_root)

    if suffix in SUPPORTED_PDF:
        decoded_lines = load_pdf_lines(str(file_path))
        return _records_from_decoded_lines(decoded_lines, file_path, data_root)

    if suffix in SUPPORTED_TXT:
        raw_lines = load_txt_lines(str(file_path))
        text_lines = clean_lines(raw_lines)
        department, office = _department_and_office_from_path(file_path, data_root)
        meta = extract_metadata(text_lines)
        auto_meta = {
            "department": department,
            "office": office,
            "source_file": str(file_path),
            **meta.to_dict(),
        }
        auto_path, sidecar_path = _metadata_paths(file_path, 0)
        resolved = resolve_metadata(auto_path, sidecar_path, auto_meta)
        return [LetterRecord(
            letter_id=_letter_id(file_path, 0),
            department=resolved.get("department", department),
            office=resolved.get("office", office),
            source_file=str(file_path),
            segment_index=0,
            text="\n".join(text_lines),
            metadata=resolved,
            low_confidence_fields=[f for f, ok in meta.field_confidence.items() if not ok],
        )]

    raise ValueError(f"Unsupported file type for ingestion: {file_path}")


def ingest_directory(data_root: Path) -> list[LetterRecord]:
    records: list[LetterRecord] = []
    supported = (*SUPPORTED_DOCX, *SUPPORTED_PDF, *SUPPORTED_TXT)
    for path in sorted(data_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in supported:
            if ".meta" in path.parts:
                continue
            records.extend(ingest_file(path, data_root))
    return records
