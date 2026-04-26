"""
Pipeline Entry Point — Scrape → Chunk → Embed → Upsert.

This module is the main entry point invoked by:
  • GitHub Actions daily cron (09:15 IST / 03:45 UTC)
  • Manual: python -m src.ingestion.run_pipeline
  • workflow_dispatch from the GitHub UI

Pipeline stages:
  Phase 4.0  Scrape   — Fetch 5 Groww pages, SHA-256 change detection
  Phase 4.1  Chunk    — GrowwPageChunker / RecursiveChunker with dedup
  Phase 4.2  Embed    — BAAI/bge-small-en-v1.5 (384-dim, L2-norm)
  Phase 4.3  Upsert   — Chroma Cloud (trychroma.com, cosine, HNSW)
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

# Load .env file automatically (created by scripts/setup_env.py).
# In CI, env vars come from GitHub Secrets — dotenv is a no-op there.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on shell env (CI path)

from src.ingestion.chunker import Chunker
from src.ingestion.embedder import Embedder
from src.ingestion.hash_store import HashStore
from src.ingestion.scraping_service import ScrapingService
from src.ingestion.url_registry import URL_REGISTRY
from src.ingestion.vector_store import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── paths (overridable via env) ─────────────────────────────────────────
_HASH_STORE_PATH = os.getenv("INGEST_HASH_STORE_PATH", "./data/hashes.json")
_RAW_HTML_DIR = os.getenv("INGEST_RAW_HTML_DIR", "./data/raw")
_SCRAPED_DIR = os.getenv("INGEST_SCRAPED_DIR", "./data/scraped")
_CHROMA_COLLECTION = os.getenv("INGEST_CHROMA_COLLECTION", "mf_faq_chunks")


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logger.info("═══ Pipeline run %s started ═══", run_id)

    # ── Phase 4.0  Scrape ───────────────────────────────────────────────
    logger.info("── Phase 4.0: Scraping ──")
    hash_store = HashStore(path=_HASH_STORE_PATH)
    scraper = ScrapingService(
        url_registry=URL_REGISTRY,
        hash_store=hash_store,
        raw_html_dir=_RAW_HTML_DIR,
    )
    scrape_summary = scraper.run()

    # Collect updated results for downstream processing
    updated_results = [r for r in scrape_summary["results"] if r.get("status") == "updated"]

    # Persist scraped content to disk
    if updated_results:
        out_dir = os.path.join(_SCRAPED_DIR, run_id)
        os.makedirs(out_dir, exist_ok=True)
        for result in updated_results:
            payload = {
                "scheme_id": result["scheme_id"],
                "content": result["content"],
                "content_hash": result["content_hash"],
                "fetched_at": result["fetched_at"],
                "metadata": result["metadata"],
            }
            fpath = os.path.join(out_dir, f"{result['scheme_id']}.json")
            with open(fpath, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)

    if not updated_results:
        logger.info("── No content changes detected — skipping chunk/embed/upsert ──")
        _log_summary(run_id, scrape_summary, chunks_total=0, embedded_total=0, upserted_total=0)
        return

    # ── Phase 4.1  Chunk ────────────────────────────────────────────────
    logger.info("── Phase 4.1: Chunking %d updated pages ──", len(updated_results))
    chunker = Chunker()
    all_chunks: list[dict] = []

    for result in updated_results:
        chunks = chunker.chunk(
            content=result["content"],
            metadata=result["metadata"],
        )
        all_chunks.extend(chunks)

    logger.info("[Pipeline] Total chunks produced: %d", len(all_chunks))

    # ── Phase 4.2  Embed ────────────────────────────────────────────────
    logger.info("── Phase 4.2: Embedding %d chunks ──", len(all_chunks))
    embedder = Embedder()
    embedded_chunks = embedder.embed_chunks(all_chunks)

    logger.info("[Pipeline] Chunks with valid embeddings: %d", len(embedded_chunks))

    # ── Phase 4.3  Upsert to Chroma Cloud ───────────────────────────────
    logger.info("── Phase 4.3: Upserting to Chroma Cloud ──")
    store = VectorStore(collection_name=_CHROMA_COLLECTION)

    # Delete old chunks for updated schemes before upserting new ones
    for result in updated_results:
        store.delete_by_source_url(result["url"])

    upserted = store.upsert_chunks(embedded_chunks)
    logger.info("[Pipeline] Chroma collection count: %d", store.count())

    # ── Manifest ────────────────────────────────────────────────────────
    if updated_results:
        out_dir = os.path.join(_SCRAPED_DIR, run_id)
        manifest = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url_count": len(URL_REGISTRY),
            "scraped": scrape_summary["scraped"],
            "updated": scrape_summary["updated"],
            "skipped": scrape_summary["skipped"],
            "errors": scrape_summary["errors"],
            "chunks_produced": len(all_chunks),
            "chunks_embedded": len(embedded_chunks),
            "chunks_upserted": upserted,
            "chroma_total": store.count(),
            "updated_schemes": [r["scheme_id"] for r in updated_results],
        }
        manifest_path = os.path.join(out_dir, "_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        logger.info("[Pipeline] Manifest → %s", manifest_path)

    # ── Summary ─────────────────────────────────────────────────────────
    _log_summary(run_id, scrape_summary, len(all_chunks), len(embedded_chunks), upserted)

    # Fail CI if too many scrape errors
    if scrape_summary["errors"] > len(URL_REGISTRY) // 2:
        logger.error("Too many errors (%d/%d) — marking run as FAILED", scrape_summary["errors"], len(URL_REGISTRY))
        sys.exit(1)


def _log_summary(run_id: str, scrape: dict, chunks_total: int, embedded_total: int, upserted_total: int) -> None:
    logger.info(
        "═══ Pipeline run %s complete ═══\n"
        "    Scrape:  scraped=%d  updated=%d  skipped=%d  errors=%d\n"
        "    Chunk:   %d chunks produced\n"
        "    Embed:   %d chunks embedded\n"
        "    Upsert:  %d chunks upserted to Chroma Cloud",
        run_id,
        scrape["scraped"], scrape["updated"], scrape["skipped"], scrape["errors"],
        chunks_total,
        embedded_total,
        upserted_total,
    )


if __name__ == "__main__":
    main()
