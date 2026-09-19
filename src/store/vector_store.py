"""Local persistent vector store -- pure Python + numpy, no native
extensions beyond numpy itself (which has solid prebuilt wheels on
every platform/architecture).

This replaces an earlier ChromaDB-based implementation. ChromaDB pulls
in a disproportionately heavy dependency tree for what this project
actually needs -- exact search over a corpus of hundreds to a few
thousand letters, not web-scale approximate nearest-neighbor search --
and that tree caused two real, unrecoverable-without-a-rewrite
problems on Windows: `chroma-hnswlib` is a C extension with no
prebuilt wheel for newer Python versions (falls back to a compile
that needs MSVC Build Tools most users don't have), and chromadb's
telemetry module unconditionally imports an OpenTelemetry gRPC
exporter at load time -- which pulls in grpcio's native DLL, which
Windows Application Control / Smart App Control blocks on a stock
machine, regardless of whether telemetry is even enabled
(`anonymized_telemetry=False` doesn't prevent the import). This store
sidesteps both by construction: nothing here needs a compiler or an
OS-level security exception to install or run, on any platform.

At this project's actual scale, brute-force cosine similarity over a
numpy matrix is fast (sub-millisecond for a few thousand rows) and
exact, rather than ChromaDB's approximate HNSW index -- a quality
improvement here, not just a compatibility one.

Persistence layout (one directory per store, e.g. VECTOR_STORE_DIR):
    vectors.npy   -- float32 array, shape (N, dim), row i = embedding for ids[i]
    records.json  -- {"ids": [...], "documents": [...], "metadatas": [...]}
    meta.json     -- {"embedding_model": ..., "embedding_dimension": ...}
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

STORE_VERSION = 1


class EmbeddingModelMismatch(RuntimeError):
    pass


def _matches(metadata: dict, where: dict | None) -> bool:
    """True if metadata satisfies every key/value in `where` (AND semantics,
    equality only) -- the only filter shape this project's retrieval
    layer actually needs (department, letter_type)."""
    if not where:
        return True
    return all(metadata.get(key) == value for key, value in where.items())


class LocalVectorStore:
    def __init__(self, persist_dir: Path, embedding_model_name: str, embedding_dimension: int):
        self._dir = Path(persist_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._vectors_path = self._dir / "vectors.npy"
        self._records_path = self._dir / "records.json"
        self._meta_path = self._dir / "meta.json"

        self._embedding_model_name = embedding_model_name
        self._embedding_dimension = embedding_dimension

        self._ids: list[str] = []
        self._documents: list[str] = []
        self._metadatas: list[dict] = []
        self._vectors: np.ndarray = np.zeros((0, embedding_dimension), dtype=np.float32)
        self._id_to_index: dict[str, int] = {}

        self._load_or_init()

    def _load_or_init(self) -> None:
        if self._meta_path.exists():
            stored = json.loads(self._meta_path.read_text(encoding="utf-8"))
            stored_model = stored.get("embedding_model")
            stored_dim = stored.get("embedding_dimension")
            if stored_model != self._embedding_model_name or stored_dim != self._embedding_dimension:
                raise EmbeddingModelMismatch(
                    f"Vector store at {self._dir} was built with embedding model "
                    f"{stored_model!r} (dim={stored_dim}) but the current config "
                    f"uses {self._embedding_model_name!r} (dim={self._embedding_dimension}). "
                    f"Re-run ingestion into a fresh VECTOR_STORE_DIR, or switch "
                    f"EMBEDDING_MODEL back."
                )
            if self._records_path.exists():
                records = json.loads(self._records_path.read_text(encoding="utf-8"))
                self._ids = records["ids"]
                self._documents = records["documents"]
                self._metadatas = records["metadatas"]
                self._id_to_index = {id_: i for i, id_ in enumerate(self._ids)}
            if self._vectors_path.exists():
                self._vectors = np.load(self._vectors_path)
        else:
            self._meta_path.write_text(
                json.dumps({
                    "version": STORE_VERSION,
                    "embedding_model": self._embedding_model_name,
                    "embedding_dimension": self._embedding_dimension,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _persist(self) -> None:
        self._records_path.write_text(
            json.dumps(
                {"ids": self._ids, "documents": self._documents, "metadatas": self._metadatas},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        np.save(self._vectors_path, self._vectors)

    def add_letters(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        if not ids:
            return
        for id_, embedding, document, metadata in zip(ids, embeddings, documents, metadatas):
            vector = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
            if id_ in self._id_to_index:
                index = self._id_to_index[id_]
                self._documents[index] = document
                self._metadatas[index] = metadata
                self._vectors[index:index + 1] = vector
            else:
                index = len(self._ids)
                self._ids.append(id_)
                self._documents.append(document)
                self._metadatas.append(metadata)
                self._id_to_index[id_] = index
                self._vectors = np.vstack([self._vectors, vector]) if self._vectors.size else vector
        self._persist()

    def count(self) -> int:
        return len(self._ids)

    def get_by_filter(self, where: dict | None) -> dict:
        indices = [i for i, meta in enumerate(self._metadatas) if _matches(meta, where)]
        return {
            "ids": [self._ids[i] for i in indices],
            "documents": [self._documents[i] for i in indices],
            "metadatas": [self._metadatas[i] for i in indices],
        }

    def get_by_ids(self, ids: list[str]) -> dict:
        indices = [self._id_to_index[i] for i in ids if i in self._id_to_index]
        return {
            "ids": [self._ids[i] for i in indices],
            "documents": [self._documents[i] for i in indices],
            "metadatas": [self._metadatas[i] for i in indices],
        }

    def delete_by_ids(self, ids: list[str]) -> None:
        remove = {i for i in ids if i in self._id_to_index}
        if not remove:
            return
        keep_indices = [i for i, id_ in enumerate(self._ids) if id_ not in remove]
        self._ids = [self._ids[i] for i in keep_indices]
        self._documents = [self._documents[i] for i in keep_indices]
        self._metadatas = [self._metadatas[i] for i in keep_indices]
        self._vectors = self._vectors[keep_indices] if keep_indices else np.zeros((0, self._embedding_dimension), dtype=np.float32)
        self._id_to_index = {id_: i for i, id_ in enumerate(self._ids)}
        self._persist()

    def delete_by_filter(self, where: dict) -> None:
        matching = self.get_by_filter(where)
        self.delete_by_ids(matching["ids"])

    def list_distinct(self, field: str) -> list[str]:
        values = {meta.get(field) for meta in self._metadatas if meta and meta.get(field)}
        return sorted(values)

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[dict]:
        indices = [i for i, meta in enumerate(self._metadatas) if _matches(meta, where)]
        if not indices:
            return []

        candidate_vectors = self._vectors[indices]
        query_vector = np.asarray(query_embedding, dtype=np.float32)

        query_norm = np.linalg.norm(query_vector)
        candidate_norms = np.linalg.norm(candidate_vectors, axis=1)
        denom = candidate_norms * query_norm
        with np.errstate(divide="ignore", invalid="ignore"):
            similarities = np.where(denom > 0, candidate_vectors @ query_vector / denom, 0.0)

        order = np.argsort(-similarities)[:top_k]
        hits = []
        for rank in order:
            i = indices[rank]
            hits.append({
                "id": self._ids[i],
                "document": self._documents[i],
                "metadata": self._metadatas[i],
                "distance": float(1.0 - similarities[rank]),
            })
        return hits
