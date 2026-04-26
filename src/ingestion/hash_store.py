"""
Hash Store — Persistent SHA-256 content hashes for change detection.

Stores a JSON mapping of { URL → SHA-256 hash } on disk so the scraping
service can detect whether a page's content has changed since the last run
and skip re-indexing when it hasn't.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class HashStore:
    """Persists content hashes to a JSON file for cross-run change detection."""

    def __init__(self, path: str = "./data/hashes.json"):
        self.path = path
        self._hashes: dict[str, str] = {}
        self._load()

    # ── public API ──────────────────────────────────────────────────────

    def get(self, url: str) -> Optional[str]:
        """Return the stored hash for *url*, or None if never seen."""
        return self._hashes.get(url)

    def set(self, url: str, content_hash: str) -> None:
        """Update the hash for *url* and persist to disk."""
        self._hashes[url] = content_hash
        self._save()

    def remove(self, url: str) -> None:
        """Remove a URL entry (e.g. when de-listed from the registry)."""
        self._hashes.pop(url, None)
        self._save()

    def all(self) -> dict[str, str]:
        """Return a copy of the full hash map."""
        return dict(self._hashes)

    # ── persistence ─────────────────────────────────────────────────────

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    self._hashes = json.load(fh)
                logger.info("[HashStore] Loaded %d hashes from %s", len(self._hashes), self.path)
            except (json.JSONDecodeError, IOError) as exc:
                logger.warning("[HashStore] Failed to load %s — starting fresh: %s", self.path, exc)
                self._hashes = {}
        else:
            logger.info("[HashStore] No existing hash file at %s — starting fresh", self.path)
            self._hashes = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._hashes, fh, indent=2)
        logger.debug("[HashStore] Saved %d hashes to %s", len(self._hashes), self.path)
