"""Hybrid retrieval: department filter -> letter-type filter -> BM25
keyword scoring -> vector-store semantic similarity -> reciprocal rank fusion.

Both the keyword and semantic passes run over the *same*
department/letter-type-filtered candidate set (fetched from the store
via a metadata-only `where` filter), so filtering always takes priority
over similarity -- an Education-department request should never surface
a Revenue letter just because it scores higher semantically.

Note: with only two real source documents in this corpus (one office
pair), this pipeline is tested for correct plumbing -- filtering,
fusion, top-k -- not for real ranking quality, which needs a broader
corpus to evaluate meaningfully. See the project plan's stated risks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from src.embeddings.base import Embedder
from src.store.vector_store import LocalVectorStore

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_RRF_K = 60


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class RetrievedLetter:
    id: str
    document: str
    metadata: dict
    fused_score: float


def _build_where(department: str | None, letter_type: str | None) -> dict | None:
    where = {}
    if department:
        where["department"] = department
    if letter_type:
        where["letter_type"] = letter_type
    return where or None


class HybridRetriever:
    def __init__(self, store: LocalVectorStore, embedder: Embedder):
        self._store = store
        self._embedder = embedder

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        department: str | None = None,
        letter_type: str | None = None,
    ) -> list[RetrievedLetter]:
        where = _build_where(department, letter_type)

        candidates = self._store.get_by_filter(where)
        candidate_ids = candidates.get("ids", [])
        candidate_docs = candidates.get("documents", [])
        candidate_metas = candidates.get("metadatas", [])

        if not candidate_ids:
            return []

        bm25_rank = self._bm25_rank(query, candidate_ids, candidate_docs)
        semantic_rank = self._semantic_rank(query, where, len(candidate_ids))

        fused_scores: dict[str, float] = {}
        for rank_list in (bm25_rank, semantic_rank):
            for rank, letter_id in enumerate(rank_list):
                fused_scores[letter_id] = fused_scores.get(letter_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

        ranked_ids = sorted(fused_scores, key=lambda i: fused_scores[i], reverse=True)[:top_k]

        id_to_doc = dict(zip(candidate_ids, candidate_docs))
        id_to_meta = dict(zip(candidate_ids, candidate_metas))
        return [
            RetrievedLetter(
                id=letter_id,
                document=id_to_doc[letter_id],
                metadata=id_to_meta[letter_id],
                fused_score=fused_scores[letter_id],
            )
            for letter_id in ranked_ids
        ]

    def _bm25_rank(self, query: str, candidate_ids: list[str], candidate_docs: list[str]) -> list[str]:
        tokenized_corpus = [_tokenize(doc) for doc in candidate_docs]
        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(_tokenize(query))
        order = sorted(range(len(candidate_ids)), key=lambda i: scores[i], reverse=True)
        return [candidate_ids[i] for i in order]

    def _semantic_rank(self, query: str, where: dict | None, limit: int) -> list[str]:
        query_embedding = self._embedder.embed([query])[0]
        hits = self._store.query(query_embedding, top_k=limit, where=where)
        return [h["id"] for h in hits]
