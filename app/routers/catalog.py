"""Department/letter-type catalog, derived from what's actually indexed."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_store
from src.store.chroma_store import ChromaLetterStore

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/departments")
def list_departments(store: ChromaLetterStore = Depends(get_store)) -> list[str]:
    return store.list_distinct("department")


@router.get("/letter-types")
def list_letter_types(store: ChromaLetterStore = Depends(get_store)) -> list[str]:
    return store.list_distinct("letter_type")
