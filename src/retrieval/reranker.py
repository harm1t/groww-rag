"""
Reranker — Phase 5.2 (lightweight lexical re-rank)

Per §5.2 of docs/rag_architecture.md:
  "Cross-encoder or lightweight lexical re-rank for table/number-heavy hits"

We use a keyword-overlap + term-frequency reranker (no external model needed).
This is intentionally lightweight:
  - No cross-encoder model download required
  - Works offline / in CI
  - Effective for fact-retrieval (NAV, expense ratio, exit load, etc.)

Upgrade path: replace score() with a cross-encoder (e.g. cross-encoder/ms-marco-MiniLM-L-6-v2)
when latency budget allows.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class RankedChunk:
    """A retrieved chunk with its final reranked score."""
    id: str
    content: str
    metadata: dict
    dense_score: float      # cosine similarity from Chroma (lower = more similar for cosine distance)
    rerank_score: float     # combined score used for final ordering
    source_url: str


class LexicalReranker:
    """Lightweight keyword-overlap reranker for Phase 5.2.

    Scores each chunk by:
      1. Term overlap between query tokens and chunk content
      2. Presence of numeric values (boosts fact-heavy chunks like NAV tables)
      3. Section-title bonus (section_title matching a query keyword)

    Final score = dense_weight * dense_sim + lexical_weight * lexical_sim
    where dense_sim is converted from cosine distance (1 - distance).
    """

    # Weight blend: dense retrieval is primary; lexical adjusts ties
    DENSE_WEIGHT = 0.65
    LEXICAL_WEIGHT = 0.35

    # Regex for detecting numeric fact content (NAV, %, ₹, Cr, etc.)
    _NUMBER_RE = re.compile(r"[\d,.]+\s*(%|₹|cr|crore|lakh|nav|sip)?", re.IGNORECASE)

    # Fact-keyword → content pattern: if the query asks for a specific fact and
    # the chunk contains matching data, the chunk almost certainly holds the answer.
    _FACT_KEYWORDS: dict[str, re.Pattern] = {
        "nav": re.compile(r"₹\s*[\d]+[.,][\d]+", re.IGNORECASE),
        "expense": re.compile(r"expense\s+ratio", re.IGNORECASE),
        "exit": re.compile(r"exit\s+load", re.IGNORECASE),
        "aum": re.compile(r"(?:AUM|Fund\s+Size)[\s:]*₹?[\d.,]+", re.IGNORECASE),
        "return": re.compile(r"\d+\s*(?:Year|Yr|Month|Mon)", re.IGNORECASE),
        "sip": re.compile(r"Min\s+SIP", re.IGNORECASE),
        "lumpsum": re.compile(r"Min\s+Lumpsum", re.IGNORECASE),
    }

    def rerank(
        self,
        query: str,
        chunks: list[RankedChunk],
    ) -> list[RankedChunk]:
        """Return chunks sorted by combined rerank_score (descending)."""
        if not chunks:
            return chunks

        query_tokens = self._tokenize(query)

        for chunk in chunks:
            lexical = self._lexical_score(query_tokens, chunk)
            # Convert cosine distance → similarity (Chroma returns distance, not similarity)
            dense_sim = max(0.0, 1.0 - chunk.dense_score)
            chunk.rerank_score = (
                self.DENSE_WEIGHT * dense_sim
                + self.LEXICAL_WEIGHT * lexical
            )

        return sorted(chunks, key=lambda c: c.rerank_score, reverse=True)

    # ── Private helpers ──────────────────────────────────────────────────

    def _lexical_score(self, query_tokens: set[str], chunk: RankedChunk) -> float:
        """Score in [0, 1] based on query-chunk keyword overlap."""
        if not query_tokens:
            return 0.0

        content_tokens = self._tokenize(chunk.content)
        overlap = len(query_tokens & content_tokens)
        term_overlap = overlap / len(query_tokens)

        # Boost if section title matches any query token (use word-level tokens to
        # avoid "fund" matching "fund_manager" for non-fund-manager queries)
        section_tokens = self._tokenize(chunk.metadata.get("section_title", ""))
        section_bonus = 0.10 if query_tokens & section_tokens else 0.0

        # Boost if chunk contains numbers (fact-heavy content)
        numeric_bonus = 0.10 if self._NUMBER_RE.search(chunk.content) else 0.0

        # Strong boost when the query asks for a specific fact and this chunk
        # contains the matching data (e.g. NAV query → chunk with ₹ price).
        fact_bonus = 0.0
        for keyword, pattern in self._FACT_KEYWORDS.items():
            if keyword in query_tokens and pattern.search(chunk.content):
                fact_bonus = 0.30
                break

        return min(1.0, term_overlap + section_bonus + numeric_bonus + fact_bonus)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Lowercase word tokens, filtering stop words and short tokens."""
        STOP_WORDS = {
            "the", "a", "an", "is", "it", "in", "of", "for", "to",
            "and", "or", "what", "how", "much", "many", "does", "do",
            "i", "me", "my", "this", "that", "are", "was", "be", "with",
        }
        tokens = re.findall(r"[a-z0-9₹%]+", text.lower())
        return {t for t in tokens if len(t) > 2 and t not in STOP_WORDS}
