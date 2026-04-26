"""
Phase 5 — Retrieval Layer public API.

Import from here rather than directly from sub-modules:

    from src.retrieval import Retriever, RetrievalResult

See docs/rag_architecture.md §5 for design rationale.
"""

from src.retrieval.query_preprocessor import PreprocessedQuery, QueryPreprocessor
from src.retrieval.reranker import LexicalReranker, RankedChunk
from src.retrieval.retriever import MergedSource, RetrievalResult, Retriever

__all__ = [
    "Retriever",
    "RetrievalResult",
    "MergedSource",
    "QueryPreprocessor",
    "PreprocessedQuery",
    "LexicalReranker",
    "RankedChunk",
]
