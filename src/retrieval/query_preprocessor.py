"""
Query Preprocessor — Phase 5.1

Handles light normalization and scheme resolution before retrieval.
Per §5.1 of docs/rag_architecture.md:
  - Light normalization: lowercase for matching; keep scheme names / tickers as entities.
  - Scheme resolution: if user names a scheme, constrain metadata filter `scheme_id`
    when confidence is high; otherwise retrieve broadly then re-rank.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# ── Scheme registry (mirrors src/ingestion/url_registry.py) ────────────────
# Maps every known alias → canonical scheme_id used in Chroma metadata.
SCHEME_ALIASES: dict[str, str] = {
    # Parag Parikh Flexi Cap / Long Term Value
    "flexi cap": "ppfas_flexi_cap",
    "flexi-cap": "ppfas_flexi_cap",
    "long term value": "ppfas_flexi_cap",
    "long-term value": "ppfas_flexi_cap",
    "ppfas flexi": "ppfas_flexi_cap",
    "parag parikh flexi": "ppfas_flexi_cap",
    "parag parikh long term": "ppfas_flexi_cap",
    # Large Cap
    "large cap": "ppfas_large_cap",
    "large-cap": "ppfas_large_cap",
    "ppfas large": "ppfas_large_cap",
    "parag parikh large": "ppfas_large_cap",
    # ELSS / Tax Saver
    "elss": "ppfas_elss",
    "tax saver": "ppfas_elss",
    "tax-saver": "ppfas_elss",
    "ppfas elss": "ppfas_elss",
    "parag parikh elss": "ppfas_elss",
    "parag parikh tax": "ppfas_elss",
    # Conservative Hybrid
    "conservative hybrid": "ppfas_conservative_hybrid",
    "conservative-hybrid": "ppfas_conservative_hybrid",
    "hybrid": "ppfas_conservative_hybrid",
    "ppfas hybrid": "ppfas_conservative_hybrid",
    "parag parikh conservative": "ppfas_conservative_hybrid",
    # Arbitrage
    "arbitrage": "ppfas_arbitrage",
    "ppfas arbitrage": "ppfas_arbitrage",
    "parag parikh arbitrage": "ppfas_arbitrage",
}

# Normalised lowercase keys for lookup
_ALIAS_LOWER: dict[str, str] = {k.lower(): v for k, v in SCHEME_ALIASES.items()}

# Match "ppfas" or "parag parikh" prefix — high confidence indicator
_PPFAS_PATTERN = re.compile(r"\b(ppfas|parag\s+parikh)\b", re.IGNORECASE)


@dataclass
class PreprocessedQuery:
    """Output of QueryPreprocessor.process()."""
    original: str                           # raw user query
    normalized: str                         # lowercased, whitespace-collapsed
    scheme_id: Optional[str] = None        # resolved scheme_id if confident
    chroma_filter: Optional[dict] = None   # ready-to-use Chroma `where` dict
    scheme_confidence: float = 0.0         # 0.0 (none) → 1.0 (exact match)
    detected_aliases: list[str] = field(default_factory=list)


class QueryPreprocessor:
    """Normalises a user query and resolves it to a specific scheme_id if confident.

    §5.1 design decisions:
    - Lowercasing for alias matching; original casing preserved in .original.
    - Longest-match alias wins (prevents "large" matching before "large cap").
    - scheme_id is only set when confidence >= threshold to avoid false narrowing.
    - chroma_filter is None when no scheme resolved → retrieves across all 5 schemes.
    """

    # Minimum confidence to apply a scheme_id filter to the Chroma query.
    # Below this threshold we retrieve broadly and rely on the reranker.
    CONFIDENCE_THRESHOLD = 0.6

    def process(self, query: str) -> PreprocessedQuery:
        """Normalize the query and optionally resolve to a scheme_id.

        Returns a PreprocessedQuery with all fields populated.
        """
        normalized = self._normalize(query)
        scheme_id, confidence, aliases = self._resolve_scheme(normalized)

        chroma_filter: Optional[dict] = None
        if scheme_id and confidence >= self.CONFIDENCE_THRESHOLD:
            chroma_filter = {"scheme_id": {"$eq": scheme_id}}

        return PreprocessedQuery(
            original=query,
            normalized=normalized,
            scheme_id=scheme_id,
            chroma_filter=chroma_filter,
            scheme_confidence=confidence,
            detected_aliases=aliases,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _normalize(query: str) -> str:
        """Lowercase, collapse whitespace. Keep entity casing for display."""
        return re.sub(r"\s+", " ", query.strip().lower())

    @staticmethod
    def _resolve_scheme(normalized: str) -> tuple[Optional[str], float, list[str]]:
        """Longest-alias-first scan to find the best matching scheme_id."""
        detected: list[tuple[str, str]] = []  # (alias, scheme_id)

        # Sort by alias length descending so longer matches win
        for alias, sid in sorted(_ALIAS_LOWER.items(), key=lambda x: -len(x[0])):
            if alias in normalized:
                detected.append((alias, sid))
                break  # take the longest match only

        if not detected:
            return None, 0.0, []

        alias, scheme_id = detected[0]

        # Boost confidence if "ppfas" or "parag parikh" also present
        confidence = 0.75
        if _PPFAS_PATTERN.search(normalized):
            confidence = 1.0

        return scheme_id, confidence, [alias]
