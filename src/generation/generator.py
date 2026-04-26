"""
Generator — Phase 6 core

Orchestrates the full generation pipeline per §6 of docs/rag_architecture.md:

  1. Build prompt (system + user turn with CONTEXT)     — §6.1
  2. Call Groq API (primary: llama-3.1-8b-instant)
  3. Validate response (§7.2):  forbidden patterns, sentence count, citation
  4. On failure → retry once with stricter prompt
  5. On retry failure → fall back to safe templated response

Required environment variable:
  GROQ_API_KEY  — get free at https://console.groq.com

Optional:
  GROQ_MODEL          (default: llama-3.1-8b-instant)
  GROQ_TEMPERATURE    (default: 0.1)
  GROQ_MAX_TOKENS     (default: 300)

Usage:
    from src.generation.generator import Generator
    gen = Generator()
    response = gen.generate(query="What is the expense ratio?", retrieval=result)
    print(response.answer_text)
    print(response.citation_url)
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from groq import Groq

from src.generation.prompt_builder import (
    ALLOWLISTED_URLS,
    SYSTEM_PROMPT,
    STRICT_RETRY_PROMPT,
    build_retry_turn,
    build_user_turn,
)
from src.generation.validator import ResponseValidator, ValidationResult
from src.retrieval.retriever import RetrievalResult

logger = logging.getLogger(__name__)

# ── Config from env ──────────────────────────────────────────────────────────
_GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
_GROQ_MODEL         = os.getenv("GROQ_MODEL",          "llama-3.1-8b-instant")
_GROQ_TEMPERATURE   = float(os.getenv("GROQ_TEMPERATURE", "0.1"))
_GROQ_MAX_TOKENS    = int(os.getenv("GROQ_MAX_TOKENS",    "300"))


# ── Result type ──────────────────────────────────────────────────────────────

@dataclass
class GenerationResult:
    """Full output of Generator.generate() — ready to return to the user."""
    query: str
    answer_text: str                    # final validated response (or fallback)
    citation_url: str                   # validated citation URL
    is_fallback: bool = False           # True if both attempts failed
    retry_used: bool = False            # True if retry was needed
    validation: ValidationResult = field(default_factory=lambda: ValidationResult(passed=True))
    raw_first_response: str = ""        # for debugging
    raw_retry_response: str = ""        # for debugging


# ── Generator ────────────────────────────────────────────────────────────────

class Generator:
    """Groq-backed generation layer for Phase 6.

    Primary model:  ``GROQ_MODEL`` (default: llama-3.1-8b-instant)

    Validates every response against the §6.2 output contract. Retries once
    with a stricter prompt on validation failure, then falls back to a safe
    templated response.
    """

    def __init__(self) -> None:
        self._validator = ResponseValidator()
        self._client = None          # lazy-loaded Groq client

    # ── Public API ───────────────────────────────────────────────────────

    def generate(self, query: str, retrieval: RetrievalResult) -> GenerationResult:
        """Generate a factual, compliant answer using Groq.

        Args:
            query:     The user's original question.
            retrieval: Output from Phase 5 Retriever.

        Returns:
            GenerationResult with validated answer_text and citation_url.
        """
        self._ensure_loaded()

        # ── No context available → safe fallback immediately ─────────────
        if not retrieval.context_text:
            logger.warning("[Generator] No retrieval context — returning safe fallback")
            return self._no_context_fallback(query, retrieval)

        # ── Attempt 1 ────────────────────────────────────────────────────
        user_turn = build_user_turn(query, retrieval)
        raw_1 = self._call_groq(SYSTEM_PROMPT, user_turn)
        logger.info("[Generator] Attempt 1 response length: %d chars", len(raw_1))

        validation_1 = self._validator.validate(raw_1, retrieval.citation_url)
        if validation_1.passed:
            logger.info("[Generator] Attempt 1 passed validation ✓")
            return GenerationResult(
                query=query,
                answer_text=raw_1.strip(),
                citation_url=validation_1.citation_url or retrieval.citation_url,
                validation=validation_1,
                raw_first_response=raw_1,
            )

        logger.warning(
            "[Generator] Attempt 1 failed validation: %s — retrying",
            validation_1.errors,
        )

        # ── Attempt 2 (stricter prompt + show failed response) ───────────
        retry_turn = build_retry_turn(query, retrieval, raw_1)
        raw_2 = self._call_groq(STRICT_RETRY_PROMPT, retry_turn)
        logger.info("[Generator] Attempt 2 response length: %d chars", len(raw_2))

        validation_2 = self._validator.validate(raw_2, retrieval.citation_url)
        if validation_2.passed:
            logger.info("[Generator] Attempt 2 passed validation ✓")
            return GenerationResult(
                query=query,
                answer_text=raw_2.strip(),
                citation_url=validation_2.citation_url or retrieval.citation_url,
                retry_used=True,
                validation=validation_2,
                raw_first_response=raw_1,
                raw_retry_response=raw_2,
            )

        logger.error(
            "[Generator] Both attempts failed validation: %s — using safe fallback",
            validation_2.errors,
        )

        # ── Fallback ─────────────────────────────────────────────────────
        return GenerationResult(
            query=query,
            answer_text=self._safe_fallback_text(retrieval),
            citation_url=retrieval.citation_url,
            is_fallback=True,
            retry_used=True,
            validation=validation_2,
            raw_first_response=raw_1,
            raw_retry_response=raw_2,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Validate API key and initialise the Groq client on first use."""
        if self._client is not None:
            return
        if not _GROQ_API_KEY:
            raise EnvironmentError(
                "[Generator] GROQ_API_KEY is not set. "
                "Get a free key at https://console.groq.com "
                "and add it to your .env file or GitHub Secrets."
            )
        self._client = Groq(api_key=_GROQ_API_KEY)
        logger.info(
            "[Generator] Groq client ready — model=%s  temperature=%.2f  max_tokens=%d",
            _GROQ_MODEL, _GROQ_TEMPERATURE, _GROQ_MAX_TOKENS,
        )

    def _call_groq(self, system: str, user_turn: str) -> str:
        """Call Groq with the configured model.

        Args:
            system: System prompt for the LLM.
            user_turn: User prompt with context.

        Returns:
            Generated response text or empty string on error.
        """
        try:
            response = self._client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_turn},
                ],
                temperature=_GROQ_TEMPERATURE,
                max_tokens=_GROQ_MAX_TOKENS,
            )
            text = response.choices[0].message.content or ""
            if text:
                logger.info("[Generator] Groq responded (%d chars)", len(text))
            return text if text else ""
        except Exception as exc:
            logger.error("[Generator] Groq API error: %s", exc)
            return ""

    @staticmethod
    def _safe_fallback_text(retrieval: RetrievalResult) -> str:
        """Safe templated response when both Groq attempts fail validation."""
        url = retrieval.citation_url or list(ALLOWLISTED_URLS)[0]
        return (
            "I was unable to generate a compliant response for that question. "
            "Please refer directly to the official scheme page for accurate information.\n\n"
            f"Source: {url}\n"
            "Last updated from sources: date unavailable"
        )

    @staticmethod
    def _no_context_fallback(query: str, retrieval: RetrievalResult) -> GenerationResult:
        """Return a safe result when the retriever found no relevant chunks."""
        url = retrieval.citation_url or list(ALLOWLISTED_URLS)[0]
        answer = (
            "I could not find relevant information for your query in the current data. "
            f"Please refer to the scheme page for accurate details.\n\n"
            f"Source: {url}\n"
            "Last updated from sources: date unavailable"
        )
        return GenerationResult(
            query=query,
            answer_text=answer,
            citation_url=url,
            is_fallback=True,
        )
