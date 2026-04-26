"""
Retriever — Phase 5 core

Orchestrates the full retrieval pipeline per §5.2 and §5.3
of docs/rag_architecture.md:

  1. QueryPreprocessor  → normalize + resolve scheme_id (§5.1)
  2. Embedder           → BGE query embedding (384-dim, QUERY_PREFIX)
  3. VectorStore.query  → dense top-K retrieval from Chroma Cloud (§5.2)
  4. LexicalReranker    → blend cosine + keyword scores (§5.2)
  5. Merge              → collapse multiple chunks per source_url (§5.3)
  6. Source selection   → pick primary citation_url (§5.3)

Usage:
    from src.retrieval.retriever import Retriever, RetrievalResult
    retriever = Retriever()
    result = retriever.retrieve("What is the expense ratio of PPFAS Flexi Cap?")
    print(result.citation_url)
    print(result.context_text)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.ingestion.embedder import Embedder
from src.ingestion.vector_store import VectorStore
from src.retrieval.query_preprocessor import PreprocessedQuery, QueryPreprocessor
from src.retrieval.reranker import LexicalReranker, RankedChunk

logger = logging.getLogger(__name__)


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class MergedSource:
    """All chunks from a single source_url, merged into one context block."""
    source_url: str
    scheme_id: str
    scheme_name: str
    fetched_at: str
    chunks: list[RankedChunk]
    combined_score: float        # max rerank_score across chunks
    context_text: str            # merged chunk text with Source URL header


@dataclass
class RetrievalResult:
    """The full output of Retriever.retrieve() — ready for the generation layer."""
    query: PreprocessedQuery
    sources: list[MergedSource]          # ranked, merged, de-duplicated
    citation_url: str                    # primary citation (§5.3)
    context_text: str                    # packed context for LLM prompt
    chunks_retrieved: int                # raw count before merge
    chunks_after_rerank: int             # count after reranking
    sources_merged: int                  # unique source_url count


# ── Retriever ────────────────────────────────────────────────────────────────

class Retriever:
    """End-to-end retrieval pipeline for Phase 5.

    Lazily initialises the embedding model and Chroma Cloud client on first
    call to retrieve() to avoid slow startup when importing.

    Args:
        top_k_dense:  Number of chunks fetched from Chroma before reranking (§5.2: 20-40).
        top_k_final:  Number of top chunks kept after reranking for LLM context.
        collection_name: Chroma collection to query (default: mf_faq_chunks).
    """

    def __init__(
        self,
        top_k_dense: int = 20,
        top_k_final: int = 5,
        collection_name: str = "mf_faq_chunks",
    ):
        self.top_k_dense = top_k_dense
        self.top_k_final = top_k_final
        self.collection_name = collection_name

        self._preprocessor = QueryPreprocessor()
        self._reranker = LexicalReranker()

        # Lazy-loaded on first call (avoids model download at import time)
        self._embedder: Optional[Embedder] = None
        self._store: Optional[VectorStore] = None

    # ── Public API ───────────────────────────────────────────────────────

    def retrieve(self, query: str) -> RetrievalResult:
        """Run the full Phase 5 retrieval pipeline.

        Args:
            query: Raw user query string.

        Returns:
            RetrievalResult with ranked sources, merged context, and citation_url.
        """
        self._ensure_loaded()

        # ── Step 1: Preprocess ───────────────────────────────────────────
        preprocessed = self._preprocessor.process(query)
        logger.info(
            "[Retriever] Query: '%s'  scheme_id=%s  confidence=%.2f",
            preprocessed.normalized,
            preprocessed.scheme_id or "broad",
            preprocessed.scheme_confidence,
        )

        # ── Step 2: Embed query ──────────────────────────────────────────
        query_vec = self._embedder.embed_query(preprocessed.normalized)

        # ── Step 3: Dense retrieval from Chroma Cloud ────────────────────
        raw_results = self._store.query(
            query_embedding=query_vec,
            n_results=self.top_k_dense,
            where=preprocessed.chroma_filter,  # None = no filter = all schemes
        )
        logger.info("[Retriever] Chroma returned %d raw chunks", len(raw_results["ids"][0]))

        # ── Step 4: Build RankedChunk list ───────────────────────────────
        chunks = self._build_chunks(raw_results)
        if not chunks:
            logger.warning("[Retriever] No chunks returned from Chroma")
            return self._empty_result(preprocessed)

        # ── Step 5: Rerank ───────────────────────────────────────────────
        reranked = self._reranker.rerank(preprocessed.normalized, chunks)
        top_chunks = reranked[: self.top_k_final]
        logger.info(
            "[Retriever] Reranked %d → kept top %d  (best score=%.3f)",
            len(reranked), len(top_chunks),
            top_chunks[0].rerank_score if top_chunks else 0.0,
        )

        # ── Step 6: Merge by source_url ──────────────────────────────────
        sources = self._merge_by_source(top_chunks)

        # ── Step 7: Select primary citation (§5.3) ───────────────────────
        citation_url = self._select_citation(sources, preprocessed)

        # ── Step 8: Pack context for LLM ─────────────────────────────────
        context_text = self._pack_context(sources)

        result = RetrievalResult(
            query=preprocessed,
            sources=sources,
            citation_url=citation_url,
            context_text=context_text,
            chunks_retrieved=len(chunks),
            chunks_after_rerank=len(top_chunks),
            sources_merged=len(sources),
        )

        logger.info(
            "[Retriever] Done — %d chunks → %d sources → citation=%s",
            len(chunks), len(sources), citation_url,
        )
        return result

    # ── Private helpers ──────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Lazy-init embedder and vector store on first call."""
        if self._embedder is None:
            logger.info("[Retriever] Loading embedder...")
            self._embedder = Embedder()
        if self._store is None:
            logger.info("[Retriever] Connecting to Chroma Cloud...")
            self._store = VectorStore(collection_name=self.collection_name)

    @staticmethod
    def _build_chunks(raw_results: dict) -> list[RankedChunk]:
        """Convert raw Chroma query results into RankedChunk objects."""
        ids = raw_results.get("ids", [[]])[0]
        docs = raw_results.get("documents", [[]])[0]
        metas = raw_results.get("metadatas", [[]])[0]
        dists = raw_results.get("distances", [[]])[0]

        chunks: list[RankedChunk] = []
        for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists):
            source_url = meta.get("source_url", "")
            chunks.append(RankedChunk(
                id=chunk_id,
                content=doc or "",
                metadata=meta or {},
                dense_score=float(dist),
                rerank_score=0.0,       # filled by reranker
                source_url=source_url,
            ))
        return chunks

    @staticmethod
    def _merge_by_source(chunks: list[RankedChunk]) -> list[MergedSource]:
        """Collapse multiple chunks from the same source_url into one MergedSource.

        §5.3: "Multiple chunks from same source_url → merge text, keep one citation URL"
        Sources are ordered by their best (max) rerank_score.
        """
        seen: dict[str, MergedSource] = {}

        for chunk in chunks:
            url = chunk.source_url
            if url not in seen:
                seen[url] = MergedSource(
                    source_url=url,
                    scheme_id=chunk.metadata.get("scheme_id", ""),
                    scheme_name=chunk.metadata.get("scheme_name", ""),
                    fetched_at=chunk.metadata.get("fetched_at", ""),
                    chunks=[chunk],
                    combined_score=chunk.rerank_score,
                    context_text="",    # filled below
                )
            else:
                seen[url].chunks.append(chunk)
                seen[url].combined_score = max(seen[url].combined_score, chunk.rerank_score)

        # Build context_text per source and sort by combined_score
        sources = sorted(seen.values(), key=lambda s: s.combined_score, reverse=True)
        for source in sources:
            merged_text = "\n\n".join(c.content for c in source.chunks)
            source.context_text = f"Source URL: {source.source_url}\n{merged_text}"

        return sources

    @staticmethod
    def _select_citation(
        sources: list[MergedSource],
        preprocessed: PreprocessedQuery,
    ) -> str:
        """Pick the single primary citation URL per §5.3.

        Primary rule: highest combined_score source.
        Conflict tie-break: prefer newer fetched_at timestamp.
        """
        if not sources:
            return ""

        # If only one source, trivial
        if len(sources) == 1:
            return sources[0].source_url

        # Primary: highest score (already sorted)
        best = sources[0]

        # If scheme was resolved with high confidence, prefer that scheme's URL
        if preprocessed.scheme_id and preprocessed.scheme_confidence >= 0.75:
            scheme_sources = [s for s in sources if s.scheme_id == preprocessed.scheme_id]
            if scheme_sources:
                best = scheme_sources[0]

        return best.source_url

    @staticmethod
    def _pack_context(sources: list[MergedSource]) -> str:
        """Pack all source context blocks into a single LLM context string.

        Each block starts with a 'Source URL:' header so the LLM can
        cite precisely without hallucinating a link.
        """
        return "\n\n---\n\n".join(s.context_text for s in sources)

    @staticmethod
    def _empty_result(preprocessed: PreprocessedQuery) -> RetrievalResult:
        """Return a safe empty result when Chroma returns nothing."""
        return RetrievalResult(
            query=preprocessed,
            sources=[],
            citation_url="",
            context_text="",
            chunks_retrieved=0,
            chunks_after_rerank=0,
            sources_merged=0,
        )
