"""Auto-detect which department a query is about, from the corpus
itself -- not a hardcoded keyword list per department (department
names aren't hardcoded anywhere else in this project either, see
data/letters/<department>/, and there's no reason to start here).

Approach: run an unfiltered hybrid retrieval pass and vote on the
department of the top-k hits. If one department doesn't clearly win,
return None rather than guess -- generate.py then searches across all
departments, same as today's default behavior. This deliberately
reuses HybridRetriever instead of building a second keyword/BM25 path,
so "which department" and "which letters" are answered by the same
retrieval logic instead of two competing implementations that could
disagree.
"""
from __future__ import annotations

from collections import Counter

from src.retrieval.hybrid import HybridRetriever

DEFAULT_TOP_K = 5
MIN_VOTE_FRACTION = 0.6  # how dominant the top department must be among top-k hits


def detect_department(
    query: str,
    retriever: HybridRetriever,
    top_k: int = DEFAULT_TOP_K,
    min_vote_fraction: float = MIN_VOTE_FRACTION,
) -> str | None:
    hits = retriever.retrieve(query, top_k=top_k)
    departments = [h.metadata.get("department") for h in hits if h.metadata.get("department")]
    if not departments:
        return None

    department, count = Counter(departments).most_common(1)[0]
    if count / len(departments) >= min_vote_fraction:
        return department
    return None
