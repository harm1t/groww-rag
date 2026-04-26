"""
Tests — Phase 6: Generation Layer

Covers:
  - PromptBuilder: system prompt content, user turn structure, context packaging
  - ResponseValidator: forbidden patterns, sentence count, URL validation, allowlist
  - Generator: retry logic, fallback, no-context path (all Gemini calls mocked)

All fast tests use mocks — no real Gemini API calls.
@pytest.mark.slow tests require GEMINI_API_KEY in env.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.generation.prompt_builder import (
    ALLOWLISTED_URLS,
    SYSTEM_PROMPT,
    build_user_turn,
    build_retry_turn,
)
from src.generation.validator import ResponseValidator, ValidationResult
from src.generation.generator import Generator, GenerationResult

# ── Shared fixtures ──────────────────────────────────────────────────────────

FLEXI_URL = "https://groww.in/mutual-funds/parag-parikh-long-term-value-fund-direct-growth"
ELSS_URL = "https://groww.in/mutual-funds/parag-parikh-elss-tax-saver-fund-direct-growth"

GOOD_RESPONSE = (
    "The expense ratio of Parag Parikh Flexi Cap Fund (Direct Plan) is 0.64% per annum. "
    "This is among the lowest in the flexi cap category.\n\n"
    f"Source: {FLEXI_URL}\n"
    "Last updated from sources: 2026-04-25T09:00:00Z"
)

ADVISORY_RESPONSE = (
    "You should invest in this fund because it outperforms its peers. "
    f"Source: {FLEXI_URL}\n"
    "Last updated from sources: 2026-04-25T09:00:00Z"
)

NO_URL_RESPONSE = (
    "The expense ratio is 0.64%.\n"
    "Last updated from sources: 2026-04-25T09:00:00Z"
)

MULTI_URL_RESPONSE = (
    f"The expense ratio is 0.64%. Source: {FLEXI_URL}\n"
    f"Also see: {ELSS_URL}\n"
    "Last updated from sources: 2026-04-25T09:00:00Z"
)

UNLISTED_URL_RESPONSE = (
    "The expense ratio is 0.64%.\n"
    "Source: https://unknown-site.com/fund\n"
    "Last updated from sources: 2026-04-25T09:00:00Z"
)


def _make_retrieval(
    context: str = "Source URL: https://groww.in/mutual-funds/parag-parikh-long-term-value-fund-direct-growth\nExpense ratio is 0.64%",
    citation_url: str = FLEXI_URL,
    fetched_at: str = "2026-04-25T09:00:00Z",
):
    """Build a minimal mock RetrievalResult."""
    from src.retrieval.retriever import RetrievalResult, MergedSource
    from src.retrieval.query_preprocessor import PreprocessedQuery

    source = MagicMock()
    source.fetched_at = fetched_at
    source.source_url = citation_url
    source.context_text = context

    pq = PreprocessedQuery(original="test", normalized="test")
    return RetrievalResult(
        query=pq,
        sources=[source],
        citation_url=citation_url,
        context_text=context,
        chunks_retrieved=1,
        chunks_after_rerank=1,
        sources_merged=1,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  PromptBuilder
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromptBuilder:

    def test_system_prompt_contains_key_rules(self):
        assert "≤ 3 sentences" in SYSTEM_PROMPT
        assert "Source:" in SYSTEM_PROMPT
        assert "Last updated from sources" in SYSTEM_PROMPT
        assert "you should" in SYSTEM_PROMPT.lower() or "not recommend" in SYSTEM_PROMPT.lower()

    def test_system_prompt_no_invest_language(self):
        # The system prompt INSTRUCTS to avoid advisory language — should not itself advise
        forbidden = ["you should invest", "buy this fund", "recommend buying"]
        for phrase in forbidden:
            assert phrase.lower() not in SYSTEM_PROMPT.lower(), f"Prompt contains: {phrase}"

    def test_build_user_turn_contains_context(self):
        retrieval = _make_retrieval()
        turn = build_user_turn("What is expense ratio?", retrieval)
        assert "CONTEXT:" in turn
        assert "0.64%" in turn

    def test_build_user_turn_contains_question(self):
        retrieval = _make_retrieval()
        turn = build_user_turn("What is expense ratio?", retrieval)
        assert "QUESTION: What is expense ratio?" in turn

    def test_build_user_turn_contains_source_url(self):
        retrieval = _make_retrieval()
        turn = build_user_turn("test", retrieval)
        assert FLEXI_URL in turn

    def test_build_user_turn_contains_metadata(self):
        retrieval = _make_retrieval()
        turn = build_user_turn("test", retrieval)
        assert "METADATA:" in turn
        assert "Data fetched at:" in turn

    def test_build_retry_turn_contains_previous_response(self):
        retrieval = _make_retrieval()
        turn = build_retry_turn("test", retrieval, "bad previous response")
        assert "bad previous response" in turn
        assert "failed compliance validation" in turn

    def test_allowlisted_urls_count(self):
        # Must have exactly 5 scheme pages + 2 educational links
        scheme_urls = [u for u in ALLOWLISTED_URLS if "groww.in" in u]
        assert len(scheme_urls) == 5, f"Expected 5 scheme URLs, got {len(scheme_urls)}"

    def test_all_allowlisted_urls_are_https(self):
        for url in ALLOWLISTED_URLS:
            assert url.startswith("https://"), f"Non-HTTPS URL: {url}"


# ═══════════════════════════════════════════════════════════════════════════════
#  ResponseValidator
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponseValidator:

    @pytest.fixture
    def v(self):
        return ResponseValidator()

    def test_good_response_passes(self, v):
        result = v.validate(GOOD_RESPONSE, FLEXI_URL)
        assert result.passed, f"Expected pass, got errors: {result.errors}"

    def test_advisory_response_fails(self, v):
        result = v.validate(ADVISORY_RESPONSE)
        assert not result.passed
        assert any("Forbidden" in e for e in result.errors)

    def test_no_url_fails(self, v):
        result = v.validate(NO_URL_RESPONSE)
        assert not result.passed
        assert any("No citation" in e for e in result.errors)

    def test_multiple_urls_fails(self, v):
        result = v.validate(MULTI_URL_RESPONSE)
        assert not result.passed
        assert any("Multiple URLs" in e for e in result.errors)

    def test_unlisted_url_fails(self, v):
        result = v.validate(UNLISTED_URL_RESPONSE)
        assert not result.passed
        assert any("allowlist" in e for e in result.errors)

    def test_citation_url_extracted(self, v):
        result = v.validate(GOOD_RESPONSE)
        assert result.citation_url == FLEXI_URL

    def test_sentence_count_tracked(self, v):
        result = v.validate(GOOD_RESPONSE)
        assert result.sentence_count >= 1

    def test_too_many_sentences_fails(self, v):
        long_response = (
            "Sentence one. Sentence two. Sentence three. "
            "Sentence four. Sentence five.\n"
            f"Source: {FLEXI_URL}\n"
            "Last updated from sources: 2026-04-25"
        )
        result = v.validate(long_response)
        # 5 sentences > 3 → should fail
        assert not result.passed
        assert any("sentences" in e for e in result.errors)

    def test_forbidden_patterns_comprehensive(self, v):
        patterns = [
            "you should invest in this",
            "I recommend this fund",
            "better than other funds",
            "guaranteed returns",
            "this fund will outperform",
        ]
        for text in patterns:
            response = f"{text}\nSource: {FLEXI_URL}\nLast updated from sources: 2026-04-25"
            result = v.validate(response)
            assert not result.passed, f"Should have failed for: {text}"

    def test_empty_response_fails(self, v):
        result = v.validate("")
        assert not result.passed

    def test_found_urls_list_populated(self, v):
        result = v.validate(GOOD_RESPONSE)
        assert FLEXI_URL in result.found_urls


# ═══════════════════════════════════════════════════════════════════════════════
#  Generator — unit tests (mocked Gemini)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGeneratorUnit:
    """Tests Generator logic without real Gemini API calls."""

    @pytest.fixture
    def gen(self, monkeypatch):
        """Generator with mocked Gemini model."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-testing")
        g = Generator()
        g._model = MagicMock()   # prevent real client init
        return g

    def _patch_gemini(self, gen, response_text: str):
        """Patch _call_gemini to return a fixed response."""
        gen._call_gemini = MagicMock(return_value=response_text)

    def test_good_response_no_retry(self, gen):
        self._patch_gemini(gen, GOOD_RESPONSE)
        retrieval = _make_retrieval()
        result = gen.generate("expense ratio?", retrieval)
        assert result.answer_text == GOOD_RESPONSE.strip()
        assert not result.retry_used
        assert not result.is_fallback
        assert gen._call_gemini.call_count == 1

    def test_bad_first_triggers_retry(self, gen):
        # First call returns advisory, second returns good
        gen._call_gemini = MagicMock(side_effect=[ADVISORY_RESPONSE, GOOD_RESPONSE])
        retrieval = _make_retrieval()
        result = gen.generate("expense ratio?", retrieval)
        assert result.retry_used
        assert not result.is_fallback
        assert gen._call_gemini.call_count == 2

    def test_both_fail_returns_fallback(self, gen):
        gen._call_gemini = MagicMock(return_value=ADVISORY_RESPONSE)
        retrieval = _make_retrieval()
        result = gen.generate("expense ratio?", retrieval)
        assert result.is_fallback
        assert result.retry_used
        assert gen._call_gemini.call_count == 2

    def test_fallback_contains_citation_url(self, gen):
        gen._call_gemini = MagicMock(return_value=ADVISORY_RESPONSE)
        retrieval = _make_retrieval()
        result = gen.generate("test", retrieval)
        assert FLEXI_URL in result.answer_text or result.citation_url == FLEXI_URL

    def test_no_context_returns_fallback_immediately(self, gen):
        gen._call_gemini = MagicMock(return_value=GOOD_RESPONSE)
        retrieval = _make_retrieval(context="", citation_url=FLEXI_URL)
        result = gen.generate("expense ratio?", retrieval)
        assert result.is_fallback
        gen._call_gemini.assert_not_called()  # no Gemini call when context is empty

    def test_result_has_query(self, gen):
        self._patch_gemini(gen, GOOD_RESPONSE)
        result = gen.generate("What is NAV?", _make_retrieval())
        assert result.query == "What is NAV?"

    def test_result_has_citation_url(self, gen):
        self._patch_gemini(gen, GOOD_RESPONSE)
        result = gen.generate("test", _make_retrieval())
        assert result.citation_url.startswith("https://")

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        import importlib
        import src.generation.generator as gmod
        importlib.reload(gmod)
        gen = gmod.Generator()
        retrieval = _make_retrieval()
        with pytest.raises(EnvironmentError, match="GEMINI_API_KEY"):
            gen.generate("test", retrieval)

    def test_gemini_api_error_triggers_fallback(self, gen):
        gen._call_gemini = MagicMock(return_value="")   # empty = failed API call
        retrieval = _make_retrieval()
        result = gen.generate("test", retrieval)
        assert result.is_fallback

    def test_raw_responses_stored(self, gen):
        gen._call_gemini = MagicMock(side_effect=[ADVISORY_RESPONSE, GOOD_RESPONSE])
        result = gen.generate("test", _make_retrieval())
        assert result.raw_first_response == ADVISORY_RESPONSE
        assert result.raw_retry_response == GOOD_RESPONSE


# ═══════════════════════════════════════════════════════════════════════════════
#  Generator — integration test (requires GEMINI_API_KEY)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestGeneratorIntegration:
    """Live test against real Gemini API. Requires GEMINI_API_KEY in .env."""

    @pytest.fixture(scope="class")
    def gen(self):
        return Generator()

    def test_expense_ratio_answer(self, gen):
        retrieval = _make_retrieval(
            context=(
                f"Source URL: {FLEXI_URL}\n"
                "Expense Ratio: The direct plan expense ratio is 0.64% per annum."
            ),
            citation_url=FLEXI_URL,
        )
        result = gen.generate("What is the expense ratio of PPFAS Flexi Cap?", retrieval)
        assert not result.is_fallback, f"Unexpected fallback: {result.answer_text}"
        assert result.citation_url.startswith("https://")
        assert "0.64" in result.answer_text or "expense" in result.answer_text.lower()

    def test_response_contains_source_line(self, gen):
        retrieval = _make_retrieval()
        result = gen.generate("What is the expense ratio?", retrieval)
        assert "Source:" in result.answer_text

    def test_response_contains_last_updated(self, gen):
        retrieval = _make_retrieval()
        result = gen.generate("What is the expense ratio?", retrieval)
        assert "Last updated" in result.answer_text

    def test_no_advisory_language_in_response(self, gen):
        retrieval = _make_retrieval()
        result = gen.generate("What is the expense ratio?", retrieval)
        forbidden = ["you should invest", "recommend", "better than", "guarantee"]
        for phrase in forbidden:
            assert phrase.lower() not in result.answer_text.lower(), \
                f"Advisory language found: '{phrase}'"
