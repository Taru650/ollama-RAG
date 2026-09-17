"""Local persistent Chroma vector store for letters.

Telemetry is explicitly disabled and Chroma's own default embedding
function is never used -- this is an offline tool, so every vector
that goes in must be precomputed by our own configured Embedder. The
embedding model name + dimension are stamped onto the collection's
metadata the first time it's created; a later mismatch (someone
switched EMBEDDING_MODEL without re-ingesting) raises loudly instead
of silently mixing incompatible vectors in the same collection.
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

COLLECTION_NAME = "letters"


class EmbeddingModelMismatch(RuntimeError):
    pass


class ChromaLetterStore:
    def __init__(self, persist_dir: Path, embedding_model_name: str, embedding_dimension: int):
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "embedding_model": embedding_model_name,
                "embedding_dimension": embedding_dimension,
            },
            embedding_function=None,
        )
        self._check_embedding_model_matches(embedding_model_name, embedding_dimension)

    def _check_embedding_model_matches(self, model_name: str, dimension: int) -> None:
        stored = self._collection.metadata or {}
        stored_model = stored.get("embedding_model")
        stored_dim = stored.get("embedding_dimension")
        if stored_model is not None and (stored_model != model_name or stored_dim != dimension):
            raise EmbeddingModelMismatch(
                f"Chroma collection was built with embedding model "
                f"{stored_model!r} (dim={stored_dim}) but the current "
                f"config uses {model_name!r} (dim={dimension}). "
                f"Re-run ingestion into a fresh CHROMA_DIR, or switch "
                f"EMBEDDING_MODEL back."
            )

    def add_letters(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self._collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def count(self) -> int:
        return self._collection.count()

    def get_by_filter(self, where: dict | None) -> dict:
        """Return all documents matching a metadata filter (no vector search)."""
        return self._collection.get(where=where or None)

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[dict]:
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where or None,
        )
        hits = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for i in range(len(ids)):
            hits.append({
                "id": ids[i],
                "document": documents[i],
                "metadata": metadatas[i],
                "distance": distances[i],
            })
        return hits
