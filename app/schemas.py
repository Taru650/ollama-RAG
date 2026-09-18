"""Pydantic request/response models for the API."""
from __future__ import annotations

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    request: str
    department: str | None = None
    letter_type: str | None = None
    facts: dict[str, str] = {}
    top_k: int | None = None


class ReferenceUsed(BaseModel):
    letter_id: str
    department: str | None
    letter_type: str | None
    subject: str | None
    snippet: str


class GenerateResponse(BaseModel):
    draft: str
    department_used: str | None
    department_auto_detected: bool
    letter_type_used: str | None
    references: list[ReferenceUsed]


class ExportRequest(BaseModel):
    draft: str


class LetterSummary(BaseModel):
    letter_id: str
    department: str
    office: str
    letter_type: str | None
    subject: str | None
    source_file: str
    needs_review: bool


class LetterDetail(LetterSummary):
    text: str
    metadata: dict


class MetadataOverride(BaseModel):
    department: str | None = None
    office: str | None = None
    letter_type: str | None = None
    subject: str | None = None


class DocumentSummary(BaseModel):
    doc_id: str
    source_file: str
    department: str
    office: str
    segment_count: int
    needs_review_count: int


class IngestSummary(BaseModel):
    letters_found: int
    letters_indexed: int
    needs_review: int
