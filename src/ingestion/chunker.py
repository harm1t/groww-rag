"""
Chunker — Routes content to the appropriate chunking strategy.

Implements:
  • GrowwPageChunker  — keyword-based section extraction for Groww fund pages
  • RecursiveChunker  — token-limited recursive splitting with overlap (fallback)
  • Chunker           — orchestrator / router with dedup and deterministic IDs

See docs/chunking-embedding-architecture.md §2–§5 for design rationale.
"""

import hashlib
import logging
from typing import List, Tuple


logger = logging.getLogger(__name__)

# ── Chunking parameters (frozen across ingest + query) ──────────────────
MAX_TOKENS = 450
MIN_TOKENS = 50
OVERLAP_TOKENS = 50


# ═══════════════════════════════════════════════════════════════════════
#  GrowwPageChunker
# ═══════════════════════════════════════════════════════════════════════

class GrowwPageChunker:
    """Extract structured sections from Groww fund pages as individual chunks.

    Groww scheme pages follow a consistent layout.  This chunker splits
    content into named sections (overview, expense_ratio, exit_load …)
    using keyword matching, then yields each section as one chunk.

    Oversized sections (>MAX_TOKENS) are re-split with RecursiveChunker.
    """

    SECTION_PATTERNS: list[tuple[str, list[str]]] = [
        ("overview",       ["fund category", "nav:", "nav ", "aum"]),
        ("expense_ratio",  ["expense ratio", "ter "]),
        ("exit_load",      ["exit load", "exit load,"]),
        ("stamp_duty_tax", ["stamp duty", "tax implication"]),
        ("sip_details",    ["minimum investment", "min. for sip", "min. for 1st"]),
        ("returns",        ["returns and rankings", "annualised returns", "historic returns"]),
        ("holdings",       ["holdings (", "holdings("]),
        ("fund_manager",   ["fund management", "fund manager"]),
        ("benchmark",      ["fund benchmark"]),
        ("risk_rating",    ["riskometer", "risk level", "very high risk", "high risk", "low risk"]),
        ("about",          ["about\n", "investment objective"]),
        ("fund_house",     ["fund house", "ppfas mutual fund\nrank"]),
    ]

    # Fact sections contain critical short data — keep even if below MIN_TOKENS
    FACT_SECTIONS = {"sip_details", "expense_ratio", "exit_load", "risk_rating", "stamp_duty_tax"}
    FACT_MIN_TOKENS = 3

    def chunk(self, content: str, metadata: dict) -> list[dict]:
        sections = self._split_by_sections(content)
        sections = self._merge_duplicate_sections(sections)
        chunks: list[dict] = []
        fallback = RecursiveChunker()

        for section_name, section_text in sections:
            text = section_text.strip()
            word_count = len(text.split())

            min_thresh = self.FACT_MIN_TOKENS if section_name in self.FACT_SECTIONS else MIN_TOKENS
            if word_count < min_thresh:
                continue

            # If too large, re-split with recursive chunker
            if word_count > MAX_TOKENS:
                sub_chunks = fallback.chunk(text, {**metadata, "section": section_name})
                chunks.extend(sub_chunks)
            else:
                chunks.append({
                    "content": text,
                    "metadata": {**metadata, "section": section_name},
                    "chunk_type": "structured",
                })

        return chunks

    def _merge_duplicate_sections(self, sections: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Merge repeated occurrences of the same section into one chunk."""
        merged: dict[str, list[str]] = {}
        order: list[str] = []
        for name, text in sections:
            if name not in merged:
                merged[name] = []
                order.append(name)
            merged[name].append(text.strip())
        return [(name, "\n".join(merged[name])) for name in order]

    def _split_by_sections(self, content: str) -> List[Tuple[str, str]]:
        """Split content into named sections based on keyword matching."""
        lines = content.split("\n")
        sections: list[tuple[str, str]] = []
        current_section = "overview"
        current_text: list[str] = []

        for line in lines:
            line_lower = line.lower().strip()
            matched = False
            for section_name, keywords in self.SECTION_PATTERNS:
                if any(kw in line_lower for kw in keywords):
                    # Flush previous section
                    if current_text:
                        sections.append((current_section, "\n".join(current_text)))
                    current_section = section_name
                    current_text = [line]
                    matched = True
                    break
            if not matched:
                current_text.append(line)

        # Flush last section
        if current_text:
            sections.append((current_section, "\n".join(current_text)))

        return sections


# ═══════════════════════════════════════════════════════════════════════
#  RecursiveChunker  (fallback)
# ═══════════════════════════════════════════════════════════════════════

class RecursiveChunker:
    """Token-limited recursive splitting with overlap.

    Splits text by progressively finer separators (``\\n\\n`` → ``\\n`` →
    ``. `` → `` ``) until every chunk is within *max_tokens*.
    """

    def __init__(
        self,
        max_tokens: int = MAX_TOKENS,
        overlap_tokens: int = OVERLAP_TOKENS,
        min_tokens: int = MIN_TOKENS,
    ):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.min_tokens = min_tokens
        self.separators = ["\n\n", "\n", ". ", " "]

    def chunk(self, content: str, metadata: dict) -> list[dict]:
        raw_chunks = self._recursive_split(content, self.separators)
        return [
            {
                "content": c.strip(),
                "metadata": {**metadata, "section": metadata.get("section", "general")},
                "chunk_type": "recursive",
            }
            for c in raw_chunks
            if len(c.split()) >= self.min_tokens
        ]

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if len(text.split()) <= self.max_tokens:
            return [text]

        sep = separators[0] if separators else " "
        parts = text.split(sep)
        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = f"{current}{sep}{part}" if current else part
            if len(candidate.split()) > self.max_tokens and current:
                chunks.append(current)
                # Overlap: carry last N tokens into next chunk
                if self.overlap_tokens:
                    overlap = " ".join(current.split()[-self.overlap_tokens:])
                    current = f"{overlap}{sep}{part}"
                else:
                    current = part
            else:
                current = candidate

        if current:
            chunks.append(current)

        # If any chunk is still too large, try next separator
        if len(separators) > 1:
            refined: list[str] = []
            for chunk in chunks:
                if len(chunk.split()) > self.max_tokens:
                    refined.extend(self._recursive_split(chunk, separators[1:]))
                else:
                    refined.append(chunk)
            return refined

        return chunks


# ═══════════════════════════════════════════════════════════════════════
#  Chunker  (router / orchestrator)
# ═══════════════════════════════════════════════════════════════════════

class Chunker:
    """Routes content to the appropriate chunking strategy based on source_type.

    After chunking, assigns deterministic IDs (for idempotent Chroma
    upserts) and deduplicates by content hash.
    """

    def __init__(self):
        self.strategies: dict[str, object] = {
            "groww_scheme_page": GrowwPageChunker(),
        }
        self.fallback = RecursiveChunker()

    def chunk(self, content: str, metadata: dict) -> list[dict]:
        """Chunk content and return a list of deduped, ID-assigned chunk dicts."""
        source_type = metadata.get("source_type", "")
        strategy = self.strategies.get(source_type, self.fallback)

        chunks = strategy.chunk(content, metadata)

        # ── Post-processing: deterministic IDs + dedup hash ─────────
        for i, chunk in enumerate(chunks):
            content_hash = hashlib.sha256(chunk["content"].encode("utf-8")).hexdigest()[:16]
            scheme_id = metadata.get("scheme_id", "unknown")
            chunk["id"] = f"{scheme_id}_{i}_{content_hash}"
            chunk["content_hash"] = content_hash
            chunk["metadata"]["chunk_index"] = i

        # ── Deduplicate by content hash ─────────────────────────────
        seen: set[str] = set()
        deduped: list[dict] = []
        for chunk in chunks:
            if chunk["content_hash"] not in seen:
                seen.add(chunk["content_hash"])
                deduped.append(chunk)

        logger.info(
            "[Chunker] %s → %d chunks (%d after dedup)",
            metadata.get("scheme_id", "?"),
            len(chunks),
            len(deduped),
        )
        return deduped
