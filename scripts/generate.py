#!/usr/bin/env python3
"""Retrieve similar letters and draft a new one with Qwen3 via Ollama.

Usage:
    python scripts/generate.py --request "शिक्षकों की कमी के संबंध में पत्र तैयार करें।" \\
        --department education --fact "विद्यालय=राजकीय मध्य विद्यालय, XYZ"

Requires a running local Ollama server with the configured model
pulled (see .env / README). This script does not run in the build
sandbox -- it needs a real Ollama server on your machine.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._console import ensure_utf8_console

ensure_utf8_console()

from config.settings import settings
from src.embeddings.factory import build_embedder
from src.generation.ollama_client import OllamaChatClient
from src.generation.prompt_builder import ReferenceLetter, build_messages
from src.retrieval.department_detector import detect_department
from src.retrieval.hybrid import HybridRetriever
from src.store.vector_store import LocalVectorStore


def parse_facts(fact_args: list[str]) -> dict[str, str]:
    facts = {}
    for item in fact_args or []:
        if "=" not in item:
            print(f"Ignoring malformed --fact (expected key=value): {item}")
            continue
        key, value = item.split("=", 1)
        facts[key.strip()] = value.strip()
    return facts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, help="Hindi description of the letter to draft")
    parser.add_argument(
        "--department",
        help="Filter retrieval to this department. If omitted, it's auto-detected "
             "from your request text by seeing which department's letters the "
             "request matches best; falls back to searching all departments if "
             "no department clearly wins.",
    )
    parser.add_argument("--letter-type", help="Filter retrieval to this letter type")
    parser.add_argument("--fact", action="append", help="key=value, repeatable")
    parser.add_argument("--top-k", type=int, default=settings.top_k)
    args = parser.parse_args()

    embedder = build_embedder(
        backend=settings.embedding_backend,
        model_name=settings.embedding_model,
        ollama_host=settings.ollama_host,
        ollama_num_ctx=settings.embedding_num_ctx,
    )
    store = LocalVectorStore(settings.vector_store_dir, embedder.model_name, embedder.dimension())
    retriever = HybridRetriever(store, embedder)

    department = args.department
    if department is None:
        department = detect_department(args.request, retriever)
        if department:
            print(f"Auto-detected department: {department} (pass --department to override)")
        else:
            print("Could not confidently auto-detect a department; searching all departments.")

    hits = retriever.retrieve(
        args.request, top_k=args.top_k, department=department, letter_type=args.letter_type
    )

    if not hits:
        print("No reference letters found for this department/letter-type filter. "
              "Generation will proceed with no references -- expect more placeholders.")

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
        user_request=args.request,
        department=department,
        letter_type=args.letter_type,
        references=references,
        extra_facts=parse_facts(args.fact),
    )

    client = OllamaChatClient(host=settings.ollama_host)
    draft = client.chat(model=settings.ollama_model, messages=messages, temperature=settings.generation_temperature)

    print("=" * 70)
    print("DRAFT")
    print("=" * 70)
    print(draft)
    print()
    print("=" * 70)
    print("REFERENCES USED")
    print("=" * 70)
    if not hits:
        print("(none)")
    for h in hits:
        print(f"- {h.metadata.get('letter_id', h.id)} "
              f"[{h.metadata.get('department')}/{h.metadata.get('letter_type')}] "
              f"subject: {h.metadata.get('subject')}")


if __name__ == "__main__":
    main()
