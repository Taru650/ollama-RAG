"""POST /api/generate -- same pipeline as scripts/generate.py, over HTTP."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_ollama_client, get_retriever
from app.schemas import GenerateRequest, GenerateResponse, ReferenceUsed
from config.settings import settings
from src.generation.ollama_client import OllamaChatClient
from src.generation.prompt_builder import ReferenceLetter, build_messages
from src.retrieval.department_detector import detect_department
from src.retrieval.hybrid import HybridRetriever

router = APIRouter(prefix="/api", tags=["generate"])

SNIPPET_LENGTH = 200


@router.post("/generate", response_model=GenerateResponse)
def generate_letter(
    body: GenerateRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    ollama_client: OllamaChatClient = Depends(get_ollama_client),
) -> GenerateResponse:
    department = body.department
    auto_detected = False
    if not department:
        department = detect_department(body.request, retriever)
        auto_detected = department is not None

    top_k = body.top_k or settings.top_k
    hits = retriever.retrieve(
        body.request, top_k=top_k, department=department, letter_type=body.letter_type
    )

    references = [
        ReferenceLetter(
            department=h.metadata.get("department", "unknown"),
            letter_type=h.metadata.get("letter_type", "unknown"),
            subject=h.metadata.get("subject"),
            text=h.document,
        )
        for h in hits
    ]

    messages = build_messages(
        user_request=body.request,
        department=department,
        letter_type=body.letter_type,
        references=references,
        extra_facts=body.facts,
    )

    draft = ollama_client.chat(
        model=settings.ollama_model, messages=messages, temperature=settings.generation_temperature
    )

    return GenerateResponse(
        draft=draft,
        department_used=department,
        department_auto_detected=auto_detected,
        letter_type_used=body.letter_type,
        references=[
            ReferenceUsed(
                letter_id=h.metadata.get("letter_id", h.id),
                department=h.metadata.get("department"),
                letter_type=h.metadata.get("letter_type"),
                subject=h.metadata.get("subject"),
                snippet=(h.document[:SNIPPET_LENGTH] + "…") if len(h.document) > SNIPPET_LENGTH else h.document,
            )
            for h in hits
        ],
    )
