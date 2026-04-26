"""
Embedder — Dense vector embedding via BAAI/bge-small-en-v1.5.

Handles both **document embedding** (ingestion) and **query embedding**
(runtime) using asymmetric prefixes for optimal retrieval accuracy.

See docs/chunking-embedding-architecture.md §6 for design rationale.
"""

import logging
import math
import os
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── Configurable via env (change REQUIRES a full re-index of data/chroma/) ──
_EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
_EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "32"))


class Embedder:
    """Embeds text chunks and queries using a local SentenceTransformer model.

    Key behaviours:
      • Uses asymmetric prefixes (DOC vs QUERY) — critical for BGE models.
      • L2-normalizes all embeddings so cosine ≈ dot product.
      • Validates vector dimensions and norms after encoding.
    """

    # Asymmetric prefixes for BGE models (critical for retrieval quality)
    DOC_PREFIX = "Represent this document for retrieval: "
    QUERY_PREFIX = "Represent this query for retrieval: "

    def __init__(
        self,
        model_name: str = _EMBED_MODEL,
        batch_size: int = _EMBED_BATCH_SIZE,
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.batch_size = batch_size

        logger.info("[Embedder] Loading model %s …", model_name)
        self.model = SentenceTransformer(model_name, device=device)
        self.dimensions = self.model.get_sentence_embedding_dimension()
        logger.info(
            "[Embedder] Loaded %s (%d-dim) on %s",
            model_name,
            self.dimensions,
            self.model.device,
        )

    # ── Document embedding (ingestion) ──────────────────────────────

    def embed_chunks(self, chunks: list[dict]) -> list[dict]:
        """Embed document chunks in batches.

        Mutates each chunk dict in-place, adding an ``"embedding"`` key
        (list[float], length = self.dimensions).  Returns the same list.
        """
        if not chunks:
            return chunks

        texts = [self.DOC_PREFIX + c["content"] for c in chunks]

        logger.info(
            "[Embedder] Embedding %d chunks (batch_size=%d) …",
            len(texts),
            self.batch_size,
        )

        all_embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 50,
        )

        # ── Validation ──────────────────────────────────────────────
        valid_chunks: list[dict] = []
        for chunk, embedding in zip(chunks, all_embeddings):
            vec = embedding.tolist()

            # Dimension check
            if len(vec) != self.dimensions:
                logger.error(
                    "[Embedder] Dimension mismatch for chunk %s: got %d, expected %d — skipping",
                    chunk.get("id", "?"), len(vec), self.dimensions,
                )
                continue

            # NaN check
            if any(math.isnan(v) for v in vec):
                logger.error("[Embedder] NaN in embedding for chunk %s — skipping", chunk.get("id", "?"))
                continue

            chunk["embedding"] = vec
            valid_chunks.append(chunk)

        logger.info("[Embedder] Successfully embedded %d / %d chunks", len(valid_chunks), len(chunks))
        return valid_chunks

    # ── Query embedding (runtime) ───────────────────────────────────

    def embed_query(self, query: str) -> list[float]:
        """Embed a single user query with query-specific prefix."""
        prefixed = self.QUERY_PREFIX + query
        embedding = self.model.encode(prefixed, normalize_embeddings=True)
        return embedding.tolist()

    # ── Utility ─────────────────────────────────────────────────────

    def compute_similarity(self, query_vec: list[float], doc_vec: list[float]) -> float:
        """Cosine similarity between two L2-normalized vectors (= dot product)."""
        q = np.array(query_vec)
        d = np.array(doc_vec)
        return float(np.dot(q, d))
