"""Admin/data-management endpoints: list, upload, view, edit metadata,
delete, and rebuild the index.

Document-level operations (upload/delete a whole source file) are kept
separate from letter-level operations (edit one segment's metadata,
drop one segment from the index without touching its source file) --
they're genuinely different things: one .docx can hold dozens of
letters (see src/ingestion/segmentation.py), so "delete this letter"
and "delete this file" are not the same action and conflating them
would be a real correctness bug, not just an API nicety.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.dependencies import get_embedder, get_retriever, get_store
from app.doc_ids import InvalidDocumentId, decode_doc_id, encode_doc_id
from app.schemas import DocumentSummary, IngestSummary, LetterDetail, LetterSummary, MetadataOverride
from config.settings import settings
from src.embeddings.base import Embedder
from src.ingestion.indexing import index_records
from src.ingestion.pipeline import (
    SUPPORTED_DOCX, SUPPORTED_PDF, SUPPORTED_TXT,
    ingest_directory, ingest_file, metadata_sidecar_paths,
)
from src.retrieval.hybrid import HybridRetriever
from src.store.vector_store import LocalVectorStore

router = APIRouter(prefix="/api/admin", tags=["admin"])

_SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SUPPORTED_UPLOAD_SUFFIXES = (*SUPPORTED_DOCX, *SUPPORTED_PDF, *SUPPORTED_TXT)


def _validate_slug(value: str, field_name: str) -> str:
    if not _SAFE_SLUG_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must contain only letters, numbers, - and _ (got {value!r})",
        )
    return value


def _safe_filename(original_name: str) -> str:
    name = Path(original_name).name  # strip any directory components
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return name


# ---------------------------------------------------------------- documents

@router.get("/documents", response_model=list[DocumentSummary])
def list_documents():
    data_root = Path(settings.data_dir)
    if not data_root.exists():
        return []
    records = ingest_directory(data_root)
    by_file: dict[str, DocumentSummary] = {}
    for r in records:
        if r.source_file not in by_file:
            by_file[r.source_file] = DocumentSummary(
                doc_id=encode_doc_id(Path(r.source_file), data_root),
                source_file=r.source_file, department=r.department, office=r.office,
                segment_count=0, needs_review_count=0,
            )
        summary = by_file[r.source_file]
        summary.segment_count += 1
        if r.needs_review:
            summary.needs_review_count += 1
    return list(by_file.values())


@router.get("/documents/{doc_id}", response_model=list[LetterDetail])
def get_document(doc_id: str):
    data_root = Path(settings.data_dir)
    try:
        file_path = decode_doc_id(doc_id, data_root)
    except InvalidDocumentId as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    records = ingest_file(file_path, data_root)
    return [
        LetterDetail(
            letter_id=r.letter_id, department=r.department, office=r.office,
            letter_type=r.metadata.get("letter_type"), subject=r.metadata.get("subject"),
            source_file=r.source_file, needs_review=r.needs_review,
            text=r.text, metadata=r.metadata,
        )
        for r in records
    ]


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, store: LocalVectorStore = Depends(get_store)):
    data_root = Path(settings.data_dir)
    try:
        file_path = decode_doc_id(doc_id, data_root)
    except InvalidDocumentId as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    store.delete_by_filter({"source_file": str(file_path)})

    meta_dir = file_path.parent / ".meta"
    for pattern in (f"{file_path.stem}__seg*.meta.auto.json", f"{file_path.stem}__seg*.meta.json"):
        for sidecar in meta_dir.glob(pattern):
            sidecar.unlink(missing_ok=True)

    file_path.unlink()
    return {"deleted": str(file_path)}


@router.post("/upload", response_model=IngestSummary)
def upload_document(
    file: UploadFile = File(...),
    department: str = Form(...),
    office: str = Form(...),
    store: LocalVectorStore = Depends(get_store),
    embedder: Embedder = Depends(get_embedder),
):
    _validate_slug(department, "department")
    _validate_slug(office, "office")
    filename = _safe_filename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {suffix!r}; expected one of {SUPPORTED_UPLOAD_SUFFIXES}",
        )

    data_root = Path(settings.data_dir)
    dest_dir = data_root / department / office
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    records = ingest_file(dest_path, data_root)
    indexed = index_records(records, store, embedder)
    needs_review = sum(1 for r in records if r.needs_review)

    return IngestSummary(letters_found=len(records), letters_indexed=indexed, needs_review=needs_review)


@router.post("/reindex", response_model=IngestSummary)
def reindex(
    store: LocalVectorStore = Depends(get_store),
    embedder: Embedder = Depends(get_embedder),
):
    data_root = Path(settings.data_dir)
    records = ingest_directory(data_root)
    indexed = index_records(records, store, embedder)
    needs_review = sum(1 for r in records if r.needs_review)
    return IngestSummary(letters_found=len(records), letters_indexed=indexed, needs_review=needs_review)


# ------------------------------------------------------------------ letters

@router.get("/letters", response_model=list[LetterSummary])
def list_letters(department: str | None = None, store: LocalVectorStore = Depends(get_store)):
    where = {"department": department} if department else None
    result = store.get_by_filter(where)
    return [
        LetterSummary(
            letter_id=meta.get("letter_id", id_), department=meta.get("department", "unknown"),
            office=meta.get("office", "unknown"), letter_type=meta.get("letter_type"),
            subject=meta.get("subject"), source_file=meta.get("source_file", ""),
            needs_review=bool(meta.get("needs_review", False)),
        )
        for id_, meta in zip(result.get("ids", []), result.get("metadatas", []))
    ]


@router.delete("/letters/{letter_id}")
def delete_letter(letter_id: str, store: LocalVectorStore = Depends(get_store)):
    existing = store.get_by_ids([letter_id])
    if not existing.get("ids"):
        raise HTTPException(status_code=404, detail="Letter not found in index")
    store.delete_by_ids([letter_id])
    return {"deleted": letter_id}


@router.patch("/letters/{letter_id}/metadata")
def update_letter_metadata(
    letter_id: str,
    overrides: MetadataOverride,
    store: LocalVectorStore = Depends(get_store),
    embedder: Embedder = Depends(get_embedder),
):
    existing = store.get_by_ids([letter_id])
    if not existing.get("ids"):
        raise HTTPException(status_code=404, detail="Letter not found in index")

    source_file = Path(existing["metadatas"][0].get("source_file", ""))
    _, sidecar_path = metadata_sidecar_paths(source_file, letter_id)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    current_overrides = {}
    if sidecar_path.exists():
        current_overrides = json.loads(sidecar_path.read_text(encoding="utf-8"))
    new_overrides = {k: v for k, v in overrides.model_dump().items() if v is not None}
    current_overrides.update(new_overrides)
    sidecar_path.write_text(json.dumps(current_overrides, ensure_ascii=False, indent=2), encoding="utf-8")

    merged_meta = dict(existing["metadatas"][0])
    merged_meta.update(new_overrides)
    document_text = existing["documents"][0]
    embedding = embedder.embed([document_text])[0]
    store.add_letters([letter_id], [embedding], [document_text], [merged_meta])

    return {"letter_id": letter_id, "metadata": merged_meta}


# ------------------------------------------------------------------- search

@router.get("/search", response_model=list[LetterSummary])
def search_letters(q: str, top_k: int = 10, retriever: HybridRetriever = Depends(get_retriever)):
    hits = retriever.retrieve(q, top_k=top_k)
    return [
        LetterSummary(
            letter_id=h.metadata.get("letter_id", h.id), department=h.metadata.get("department", "unknown"),
            office=h.metadata.get("office", "unknown"), letter_type=h.metadata.get("letter_type"),
            subject=h.metadata.get("subject"), source_file=h.metadata.get("source_file", ""),
            needs_review=bool(h.metadata.get("needs_review", False)),
        )
        for h in hits
    ]
