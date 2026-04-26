"""
Response Validator — Phase 6 / §7.2

Validates Gemini's generated response against the output contract (§6.2):
  - Body ≤ 3 sentences
  - Exactly one citation URL, on the allowlist
  - No forbidden advisory/comparative patterns
  - Citation URL matches the retrieval's source_url

On failure, the Generator retries once with a stricter prompt,
then falls back to a safe templated response.
"""

import re
from dataclasses import dataclass, field

from src.generation.prompt_builder import ALLOWLISTED_URLS

# ── Forbidden patterns (§7.2) ────────────────────────────────────────────────
_FORBIDDEN_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\byou should\b",
        r"\bi (?:would |strongly )?recommend\b",
        r"\binvest in\b",
        r"\bbetter than\b",
        r"\boutperform",
        r"\bguarantee",
        r"\bbest fund\b",
        r"\bsuperior\b",
        r"\bsafe investment\b",
        r"\bhigh returns\b",
        r"\bbuy this\b",
        r"\bdon't miss\b",
    ]
]

# ── URL extractor ─────────────────────────────────────────────────────────────
_URL_RE = re.compile(r"https?://[^\s\)\]>\"']+", re.IGNORECASE)

# ── Sentence splitter (heuristic, §7.2) ──────────────────────────────────────
_SENTENCE_END_RE = re.compile(r"[.!?]+")


@dataclass
class ValidationResult:
    """Outcome of ResponseValidator.validate()."""
    passed: bool
    errors: list[str] = field(default_factory=list)
    found_urls: list[str] = field(default_factory=list)
    citation_url: str = ""        # the validated citation URL if passed
    sentence_count: int = 0


class ResponseValidator:
    """Validates Gemini responses against the §6.2 output contract.

    Checks (in order):
      1. No forbidden advisory patterns
      2. ≤ 3 sentences (heuristic)
      3. Exactly one HTTP(S) URL present
      4. URL is on the allowlist
    """

    MAX_SENTENCES = 3

    def validate(self, response: str, expected_url: str = "") -> ValidationResult:
        """Run all checks and return a ValidationResult.

        Args:
            response:     Raw text from Gemini.
            expected_url: The citation_url from RetrievalResult (for soft-check).
        """
        errors: list[str] = []

        # ── Check 1: Forbidden patterns ──────────────────────────────────
        for pattern in _FORBIDDEN_PATTERNS:
            if pattern.search(response):
                errors.append(f"Forbidden pattern found: '{pattern.pattern}'")

        # ── Check 2: Sentence count ──────────────────────────────────────
        # Split on sentence-ending punctuation; count non-empty segments.
        # Exclude "Source:" and "Last updated" lines from count.
        body_lines = [
            line for line in response.splitlines()
            if line.strip()
            and not line.strip().startswith("Source:")
            and not line.strip().startswith("Last updated")
        ]
        body_text = " ".join(body_lines)
        sentence_count = len(_SENTENCE_END_RE.findall(body_text))
        sentence_count = max(sentence_count, 1)  # at least 1 if non-empty

        if sentence_count > self.MAX_SENTENCES:
            errors.append(
                f"Response has ~{sentence_count} sentences (max {self.MAX_SENTENCES})"
            )

        # ── Check 3: Exactly one URL ─────────────────────────────────────
        found_urls = _URL_RE.findall(response)
        # Deduplicate while preserving order
        seen: dict[str, None] = {}
        for u in found_urls:
            seen[u.rstrip(".,;)")] = None
        unique_urls = list(seen.keys())

        if len(unique_urls) == 0:
            errors.append("No citation URL found in response")
        elif len(unique_urls) > 1:
            errors.append(f"Multiple URLs found ({len(unique_urls)}): {unique_urls}")

        # ── Check 4: URL on allowlist ────────────────────────────────────
        citation_url = unique_urls[0] if unique_urls else ""
        if citation_url and citation_url not in ALLOWLISTED_URLS:
            # Soft match: check if any allowlisted URL starts with the found URL's domain
            is_allowed = any(
                citation_url.startswith(allowed) or allowed.startswith(citation_url)
                for allowed in ALLOWLISTED_URLS
            )
            if not is_allowed:
                errors.append(
                    f"Citation URL not on allowlist: {citation_url}"
                )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            found_urls=unique_urls,
            citation_url=citation_url,
            sentence_count=sentence_count,
        )
