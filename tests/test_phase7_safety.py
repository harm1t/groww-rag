"""
Tests for Phase 7 — Safety & Refusal Layer

Tests:
- Intent router classification (factual vs advisory vs out-of-scope)
- PII detector (PAN, Aadhaar, email, phone, OTP, account numbers)
- Safety orchestrator end-to-end pipeline
"""

import pytest

from src.safety import (
    ADVISORY_REFUSAL,
    IntentRouter,
    OUT_OF_SCOPE_REFUSAL,
    PIIDetector,
    PII_REFUSAL,
    QueryIntent,
    RouterResult,
)


class TestIntentRouter:
    """Test the IntentRouter class."""

    def test_factual_query(self):
        """Test that factual queries are classified correctly."""
        router = IntentRouter()
        result = router.classify("What is the NAV of Parag Parikh Flexi Cap Fund?")
        assert result.intent == QueryIntent.FACTUAL
        assert result.confidence > 0

    def test_advisory_should_i(self):
        """Test detection of 'should I' advisory pattern."""
        router = IntentRouter()
        result = router.classify("Should I invest in Parag Parikh Flexi Cap Fund?")
        assert result.intent == QueryIntent.ADVISORY
        assert "should i" in result.reason.lower()

    def test_advisory_recommend(self):
        """Test detection of 'recommend' advisory pattern."""
        router = IntentRouter()
        result = router.classify("Which fund would you recommend for long term?")
        assert result.intent == QueryIntent.ADVISORY
        assert "recommend" in result.reason.lower()

    def test_advisory_which_is_better(self):
        """Test detection of 'which is better' comparison pattern."""
        router = IntentRouter()
        result = router.classify("Which is better, Flexi Cap or Large Cap fund?")
        assert result.intent == QueryIntent.ADVISORY
        assert "better" in result.reason.lower()

    def test_advisory_personal_situation(self):
        """Test detection of personal situation (age-based) patterns."""
        router = IntentRouter()
        result = router.classify("I am 45 years old, which fund should I choose?")
        assert result.intent == QueryIntent.ADVISORY
        assert "personal situation" in result.reason.lower()

    def test_advisory_retirement(self):
        """Test detection of retirement planning patterns."""
        router = IntentRouter()
        result = router.classify("I'm retiring in 5 years, what should I invest in?")
        assert result.intent == QueryIntent.ADVISORY

    def test_out_of_scope_stock(self):
        """Test detection of stock-related out-of-scope queries."""
        router = IntentRouter()
        result = router.classify("Should I buy Reliance stock?")
        assert result.intent == QueryIntent.OUT_OF_SCOPE

    def test_out_of_scope_crypto(self):
        """Test detection of cryptocurrency out-of-scope queries."""
        router = IntentRouter()
        result = router.classify("Is Bitcoin a good investment?")
        assert result.intent == QueryIntent.OUT_OF_SCOPE

    def test_out_of_scope_real_estate(self):
        """Test detection of real estate out-of-scope queries."""
        router = IntentRouter()
        result = router.classify("Should I invest in real estate?")
        assert result.intent == QueryIntent.OUT_OF_SCOPE

    def test_comparison_multiple_patterns(self):
        """Test that multiple comparison patterns trigger advisory."""
        router = IntentRouter()
        result = router.classify("Compare fund A vs fund B or fund C")
        assert result.intent == QueryIntent.ADVISORY


class TestPIIDetector:
    """Test the PIIDetector class."""

    def test_no_pii(self):
        """Test that queries without PII are not flagged."""
        detector = PIIDetector()
        result = detector.detect("What is the NAV of Parag Parikh Flexi Cap Fund?")
        assert result.has_pii is False
        assert result.pii_type == ""

    def test_pii_pan(self):
        """Test detection of PAN numbers."""
        detector = PIIDetector()
        result = detector.detect("My PAN is ABCDE1234F")
        assert result.has_pii is True
        assert result.pii_type == "PAN"

    def test_pii_pan_lowercase(self):
        """Test detection of PAN numbers with lowercase."""
        detector = PIIDetector()
        result = detector.detect("My pan is abcde1234f")
        assert result.has_pii is True
        assert result.pii_type == "PAN"

    def test_pii_aadhaar(self):
        """Test detection of Aadhaar numbers."""
        detector = PIIDetector()
        result = detector.detect("My Aadhaar is 1234 5678 9012")
        assert result.has_pii is True
        assert result.pii_type == "Aadhaar"

    def test_pii_aadhaar_no_spaces(self):
        """Test detection of Aadhaar numbers without spaces."""
        detector = PIIDetector()
        result = detector.detect("My Aadhaar is 123456789012")
        assert result.has_pii is True
        assert result.pii_type == "Aadhaar"

    def test_pii_email(self):
        """Test detection of email addresses."""
        detector = PIIDetector()
        result = detector.detect("Contact me at user@example.com")
        assert result.has_pii is True
        assert result.pii_type == "Email"

    def test_pii_phone(self):
        """Test detection of Indian phone numbers."""
        detector = PIIDetector()
        result = detector.detect("Call me at 9876543210")
        assert result.has_pii is True
        assert result.pii_type == "Phone"

    def test_pii_phone_with_code(self):
        """Test detection of phone numbers with country code."""
        detector = PIIDetector()
        result = detector.detect("Call me at +91 9876543210")
        assert result.has_pii is True
        assert result.pii_type == "Phone"

    def test_pii_otp(self):
        """Test detection of OTP codes."""
        detector = PIIDetector()
        result = detector.detect("My OTP is 123456")
        assert result.has_pii is True
        assert result.pii_type == "OTP"

    def test_pii_otp_with_context(self):
        """Test detection of OTP with context keywords."""
        detector = PIIDetector()
        result = detector.detect("The verification code is 789012")
        assert result.has_pii is True
        assert result.pii_type == "OTP"

    def test_pii_account_number(self):
        """Test detection of account numbers with context."""
        detector = PIIDetector()
        result = detector.detect("My account number is 1234567890123456")
        assert result.has_pii is True
        assert result.pii_type == "Account Number"

    def test_no_false_positive_nav(self):
        """Test that NAV values are not flagged as account numbers."""
        detector = PIIDetector()
        result = detector.detect("The NAV is 45.67")
        assert result.has_pii is False

    def test_no_false_positive_aum(self):
        """Test that AUM values are not flagged as account numbers."""
        detector = PIIDetector()
        result = detector.detect("The AUM is 1500 Cr")
        assert result.has_pii is False


class TestRefusalResponses:
    """Test the pre-configured refusal responses."""

    def test_advisory_refusal_content(self):
        """Test that advisory refusal contains educational link."""
        assert "amfiindia.com" in ADVISORY_REFUSAL.lower()
        assert "cannot provide investment advice" in ADVISORY_REFUSAL.lower()

    def test_out_of_scope_refusal_content(self):
        """Test that out-of-scope refusal contains educational link."""
        assert "sebi.gov.in" in OUT_OF_SCOPE_REFUSAL.lower()
        assert "outside the scope" in OUT_OF_SCOPE_REFUSAL.lower()

    def test_pii_refusal_content(self):
        """Test that PII refusal mentions privacy."""
        assert "privacy" in PII_REFUSAL.lower()
        assert "personal information" in PII_REFUSAL.lower()


class TestSafetyOrchestratorIntegration:
    """Integration tests for SafetyOrchestrator (with mocks)."""

    def test_pii_rejection(self):
        """Test that queries with PII are rejected early."""
        from src.safety import SafetyOrchestrator, SafetyResult
        from unittest.mock import Mock

        # Create mock retriever and generator
        mock_retriever = Mock()
        mock_generator = Mock()

        orchestrator = SafetyOrchestrator(
            retriever=mock_retriever,
            generator=mock_generator,
        )

        result = orchestrator.answer("My PAN is ABCDE1234F")

        assert result.was_refused is True
        assert "PII" in result.refusal_reason
        assert result.pii_result.has_pii is True
        # Retriever and generator should not be called
        mock_retriever.retrieve.assert_not_called()
        mock_generator.generate.assert_not_called()

    def test_advisory_refusal(self):
        """Test that advisory queries are refused without retrieval."""
        from src.safety import SafetyOrchestrator
        from unittest.mock import Mock

        mock_retriever = Mock()
        mock_generator = Mock()

        orchestrator = SafetyOrchestrator(
            retriever=mock_retriever,
            generator=mock_generator,
        )

        result = orchestrator.answer("Should I invest in this fund?")

        assert result.was_refused is True
        assert "Advisory" in result.refusal_reason
        assert result.router_result.intent == QueryIntent.ADVISORY
        # Retriever and generator should not be called
        mock_retriever.retrieve.assert_not_called()
        mock_generator.generate.assert_not_called()

    def test_out_of_scope_refusal(self):
        """Test that out-of-scope queries are refused without retrieval."""
        from src.safety import SafetyOrchestrator
        from unittest.mock import Mock

        mock_retriever = Mock()
        mock_generator = Mock()

        orchestrator = SafetyOrchestrator(
            retriever=mock_retriever,
            generator=mock_generator,
        )

        result = orchestrator.answer("Should I buy Bitcoin?")

        assert result.was_refused is True
        assert "Out-of-scope" in result.refusal_reason
        assert result.router_result.intent == QueryIntent.OUT_OF_SCOPE
        # Retriever and generator should not be called
        mock_retriever.retrieve.assert_not_called()
        mock_generator.generate.assert_not_called()
