"""
Vector Store — Chroma Cloud (trychroma.com) wrapper.

Uses chromadb.CloudClient so vectors live in the fully-managed Chroma Cloud.
The same collection is shared between the GitHub Actions ingest job and the
API server at query time — no local disk, no file sync required.

Required environment variables:
  CHROMA_API_KEY      — Chroma Cloud API key (from trychroma.com dashboard)
  CHROMA_TENANT       — Tenant name shown in Chroma Cloud dashboard
  CHROMA_DATABASE     — Database name within the tenant

Optional:
  INGEST_CHROMA_COLLECTION — Collection name (default: mf_faq_chunks)
  CHROMA_HOST              — Override cloud host (default: api.trychroma.com)

WARNING: CHROMA_API_KEY must NEVER be committed to the repository.
         Add to GitHub Secrets for CI; use .env (gitignored) for local dev.

WARNING: The embedding model (BAAI/bge-small-en-v1.5, 384-dim) and collection
         name must stay frozen. Changing either requires deleting the Chroma Cloud
         collection and re-running the full pipeline from scratch.

See docs/chunking-embedding-architecture.md §7 and docs/rag_architecture.md §4.3
for design rationale.
"""

import logging
import os
from typing import Optional

import chromadb

logger = logging.getLogger(__name__)

# ── Required Chroma Cloud credentials ──────────────────────────────────
_CHROMA_API_KEY = os.getenv("CHROMA_API_KEY", "")
_CHROMA_TENANT = os.getenv("CHROMA_TENANT", "")
_CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "")
_CHROMA_HOST = os.getenv("CHROMA_HOST", "api.trychroma.com")

# ── Collection config ───────────────────────────────────────────────────
_COLLECTION_NAME = os.getenv("INGEST_CHROMA_COLLECTION", "mf_faq_chunks")


def _build_client() -> chromadb.CloudClient:
    """Instantiate a Chroma Cloud client from environment credentials.

    Raises EnvironmentError with a clear message if any required secret is missing,
    so the CI job fails early with a descriptive error rather than a cryptic auth failure.
    """
    missing = [
        name for name, val in [
            ("CHROMA_API_KEY", _CHROMA_API_KEY),
            ("CHROMA_TENANT", _CHROMA_TENANT),
            ("CHROMA_DATABASE", _CHROMA_DATABASE),
        ]
        if not val
    ]
    if missing:
        raise EnvironmentError(
            f"[VectorStore] Missing required Chroma Cloud credential(s): {missing}. "
            "Set them in GitHub Secrets (for CI) or in .env (for local dev). "
            "See docs/rag_architecture.md §4.3 for details."
        )

    logger.info(
        "[VectorStore] Connecting to Chroma Cloud — tenant=%s  database=%s  host=%s",
        _CHROMA_TENANT, _CHROMA_DATABASE, _CHROMA_HOST,
    )
    return chromadb.CloudClient(
        tenant=_CHROMA_TENANT,
        database=_CHROMA_DATABASE,
        api_key=_CHROMA_API_KEY,
        cloud_host=_CHROMA_HOST,
    )


class VectorStore:
    """Thin wrapper around a Chroma Cloud collection.

    Provides idempotent upsert, scoped deletion, cosine-similarity query,
    and diagnostic helpers.  All operations are remote (no local disk).
    """

    def __init__(self, collection_name: str = _COLLECTION_NAME):
        self.collection_name = collection_name
        self.client = _build_client()

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",          # Distance metric
                "hnsw:M": 16,                    # HNSW graph connections
                "hnsw:construction_ef": 200,     # Build-time accuracy
                "hnsw:search_ef": 100,           # Query-time accuracy
            },
        )

        logger.info(
            "[VectorStore] Collection '%s' ready on Chroma Cloud (current count: %d)",
            collection_name,
            self.collection.count(),
        )

    # ── Write operations ────────────────────────────────────────────────

    def upsert_chunks(self, chunks: list[dict]) -> int:
        """Upsert embedded chunks into the Chroma Cloud collection.

        Each chunk dict must have: ``id``, ``embedding``, ``content``, ``metadata``.
        Idempotent — re-running with the same IDs updates existing records in-place.
        Returns the number of chunks upserted.
        """
        if not chunks:
            return 0

        self.collection.upsert(
            ids=[c["id"] for c in chunks],
            embeddings=[c["embedding"] for c in chunks],
            documents=[c["content"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )

        logger.info("[VectorStore] Upserted %d chunks -> '%s'", len(chunks), self.collection_name)
        return len(chunks)

    def delete_by_source_url(self, source_url: str) -> None:
        """Delete all chunks for a given source URL before re-upserting."""
        if self.collection.count() == 0:
            return
        self.collection.delete(where={"source_url": source_url})
        logger.info("[VectorStore] Deleted stale chunks for source_url=%s", source_url)

    def delete_by_scheme_id(self, scheme_id: str) -> None:
        """Delete all chunks for a given scheme (e.g. on registry removal)."""
        if self.collection.count() == 0:
            return
        self.collection.delete(where={"scheme_id": scheme_id})
        logger.info("[VectorStore] Deleted chunks for scheme_id=%s", scheme_id)

    # ── Read operations (query-time) ────────────────────────────────────

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> dict:
        """Retrieve top-k chunks by cosine similarity from Chroma Cloud.

        Returns raw Chroma result dict: ``ids``, ``documents``, ``metadatas``, ``distances``.
        """
        total = self.collection.count()
        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, max(total, 1)),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        return self.collection.query(**kwargs)

    # ── Diagnostics ─────────────────────────────────────────────────────

    def count(self) -> int:
        """Return total number of chunks in the cloud collection."""
        return self.collection.count()

    def peek(self, n: int = 5) -> dict:
        """Return a sample of stored chunks for debugging / smoke-test."""
        return self.collection.peek(limit=n)
