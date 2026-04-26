"""
Scraping Service — Core data fetcher for the ingestion pipeline.

For each URL in the registry this service:
  1. Fetches the page (HTTP GET with retry + exponential backoff).
  2. Parses HTML and strips boilerplate (nav, footer, scripts).
  3. Computes a SHA-256 hash and compares with the previous run.
  4. If changed → saves raw HTML to disk → returns extracted content.
  5. If unchanged → skips (no re-indexing needed).

The service is *not* a general-purpose crawler: it only visits URLs
explicitly listed in the URL registry.  Query-time retrieval never
calls the live web.
"""

import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.ingestion.hash_store import HashStore

logger = logging.getLogger(__name__)

# ── configurable via env ────────────────────────────────────────────────
_USER_AGENT = os.getenv(
    "INGEST_USER_AGENT",
    "PPFAS-MF-FAQ-Bot/1.0 (Data Refresh; +https://github.com/your-org/groww-mf-faq)",
)
_RAW_HTML_DIR = os.getenv("INGEST_RAW_HTML_DIR", "./data/raw")
_REQUEST_TIMEOUT = int(os.getenv("INGEST_REQUEST_TIMEOUT", "30"))
_RATE_LIMIT_SECS = float(os.getenv("INGEST_RATE_LIMIT_SECS", "2.0"))


class ScrapingService:
    """Fetches web pages, detects changes, and persists raw HTML."""

    def __init__(
        self,
        url_registry: list[dict],
        hash_store: HashStore,
        raw_html_dir: str = _RAW_HTML_DIR,
    ):
        self.url_registry = url_registry
        self.hash_store = hash_store
        self.raw_html_dir = raw_html_dir

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _USER_AGENT})

    # ── public entry point ──────────────────────────────────────────────

    def run(self) -> dict:
        """
        Scrape every URL in the registry.

        Returns a summary dict::

            {"scraped": N, "updated": N, "skipped": N, "errors": N,
             "results": [ {url, scheme_id, status, content, ...}, ... ]}
        """
        logger.info(
            "[ScrapingService] Starting scrape of %d URLs at %s",
            len(self.url_registry),
            datetime.now(timezone.utc).isoformat(),
        )

        summary = {"scraped": 0, "updated": 0, "skipped": 0, "errors": 0, "results": []}

        for entry in self.url_registry:
            try:
                result = self._scrape_one(entry)
                summary["scraped"] += 1

                if result["status"] == "updated":
                    summary["updated"] += 1
                else:
                    summary["skipped"] += 1

                summary["results"].append(result)

            except Exception as exc:
                logger.error("[ScrapingService] Failed for %s: %s", entry["url"], exc)
                summary["errors"] += 1
                summary["results"].append(
                    {"url": entry["url"], "scheme_id": entry["scheme_id"], "status": "error", "error": str(exc)}
                )

            # polite rate-limiting between requests
            time.sleep(_RATE_LIMIT_SECS)

        logger.info("[ScrapingService] Scrape complete: %s", {k: v for k, v in summary.items() if k != "results"})
        return summary

    # ── internals ───────────────────────────────────────────────────────

    def _scrape_one(self, entry: dict) -> dict:
        """Fetch a single URL, detect change, persist raw HTML if changed."""
        url = entry["url"]
        scheme_id = entry["scheme_id"]

        # Step 1: Fetch with retry
        response = self._fetch_with_retry(url)
        raw_html = response.text

        # Step 2: Parse and extract main content
        soup = BeautifulSoup(raw_html, "html.parser")
        content = self._extract_content(soup, entry["source_type"])

        # Step 3: SHA-256 change detection
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        previous_hash = self.hash_store.get(url)

        if content_hash == previous_hash:
            logger.info("[ScrapingService] No changes for %s (%s)", scheme_id, url)
            return {"url": url, "scheme_id": scheme_id, "status": "skipped", "content_hash": content_hash}

        logger.info("[ScrapingService] Changes detected for %s (%s)", scheme_id, url)

        # Step 4: Persist raw HTML to disk for audit / replay
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        self._save_raw_html(raw_html, scheme_id, fetched_at)

        # Step 5: Update hash store
        self.hash_store.set(url, content_hash)

        return {
            "url": url,
            "scheme_id": scheme_id,
            "status": "updated",
            "content": content,
            "content_hash": content_hash,
            "fetched_at": fetched_at,
            "metadata": {
                "source_url": url,
                "scheme_name": entry["scheme_name"],
                "scheme_id": scheme_id,
                "amc": entry["amc"],
                "source_type": entry["source_type"],
                "category": entry.get("category", ""),
                "sub_category": entry.get("sub_category", ""),
                "last_scraped": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            },
        }

    # ── HTTP fetch with retry + backoff ─────────────────────────────────

    def _fetch_with_retry(self, url: str, max_retries: int = 3) -> requests.Response:
        """Fetch URL with exponential backoff (5 s, 10 s, 20 s)."""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=_REQUEST_TIMEOUT)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                if attempt == max_retries - 1:
                    raise
                wait = (2 ** attempt) * 5
                logger.warning(
                    "[ScrapingService] Retry %d/%d for %s in %ds: %s",
                    attempt + 1, max_retries, url, wait, exc,
                )
                time.sleep(wait)
        # unreachable, but keeps mypy happy
        raise RuntimeError(f"All {max_retries} retries exhausted for {url}")

    # ── HTML content extraction ─────────────────────────────────────────

    @staticmethod
    def _extract_content(soup: BeautifulSoup, source_type: str) -> str:
        """Strip boilerplate and return main textual content."""
        # Remove non-content elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()

        if source_type == "groww_scheme_page":
            # Groww-specific: prefer <main> or the primary container
            main = soup.find("main") or soup.find("div", class_="container")
            if main:
                return main.get_text(separator="\n", strip=True)

        # Fallback: entire <body> text
        body = soup.find("body")
        return body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)

    # ── raw HTML persistence ────────────────────────────────────────────

    def _save_raw_html(self, html: str, scheme_id: str, fetched_at: str) -> str:
        """Write raw HTML to data/raw/<scheme_id>/<fetched_at>.html."""
        dir_path = os.path.join(self.raw_html_dir, scheme_id)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"{fetched_at}.html")
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        logger.debug("[ScrapingService] Saved raw HTML → %s", file_path)
        return file_path
