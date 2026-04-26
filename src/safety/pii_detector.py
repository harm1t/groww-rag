"""
PII Detector — Phase 7.3

Detects personally identifiable information (PII) in user queries.
Per §7.3: Do not request or store PAN, Aadhaar, account numbers, OTPs, email, phone.

If PII is detected, the query should be rejected with a privacy-focused refusal.
"""

import re
from dataclasses import dataclass


@dataclass
class PIIDetectionResult:
    """Result of PII detection."""
    has_pii: bool
    pii_type: str = ""
    reason: str = ""


class PIIDetector:
    """Detects PII patterns in user queries.

    Per §7.3 Privacy requirements:
    - PAN (Permanent Account Number): 10 characters, pattern ABCDE1234F
    - Aadhaar: 12 digits
    - Account numbers: 9-18 digit sequences
    - OTP: 4-6 digit codes
    - Email: standard email pattern
    - Phone: 10-digit Indian phone numbers
    """

    # PAN pattern: 5 letters + 4 digits + 1 letter
    _PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", re.IGNORECASE)

    # Aadhaar pattern: 12 digits (may have spaces or dashes)
    _AADHAAR_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")

    # Account number pattern: 9-18 consecutive digits
    _ACCOUNT_PATTERN = re.compile(r"\b\d{9,18}\b")

    # OTP pattern: 4-6 digit codes (often preceded by "OTP" or "code")
    _OTP_PATTERN = re.compile(r"\b(?:otp|code|verification)[:\s]*(?:is\s+)?\d{4,6}\b", re.IGNORECASE)

    # Email pattern
    _EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

    # Phone pattern: Indian phone numbers (with or without +91)
    _PHONE_PATTERN = re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b")

    def detect(self, query: str) -> PIIDetectionResult:
        """Detect PII in user query.

        Args:
            query: User's input query.

        Returns:
            PIIDetectionResult indicating whether PII was found and what type.
        """
        # Check for PAN
        if self._PAN_PATTERN.search(query):
            return PIIDetectionResult(
                has_pii=True,
                pii_type="PAN",
                reason="PAN (Permanent Account Number) detected in query"
            )

        # Check for Aadhaar
        if self._AADHAAR_PATTERN.search(query):
            return PIIDetectionResult(
                has_pii=True,
                pii_type="Aadhaar",
                reason="Aadhaar number detected in query"
            )

        # Check for OTP
        if self._OTP_PATTERN.search(query):
            return PIIDetectionResult(
                has_pii=True,
                pii_type="OTP",
                reason="OTP/verification code detected in query"
            )

        # Check for email
        if self._EMAIL_PATTERN.search(query):
            return PIIDetectionResult(
                has_pii=True,
                pii_type="Email",
                reason="Email address detected in query"
            )

        # Check for phone
        if self._PHONE_PATTERN.search(query):
            return PIIDetectionResult(
                has_pii=True,
                pii_type="Phone",
                reason="Phone number detected in query"
            )

        # Check for account numbers (more lenient - only if context suggests)
        # This is a heuristic to avoid false positives on NAV/AUM values
        account_context_keywords = ["account", "account number", "acc no", "bank account"]
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in account_context_keywords):
            if self._ACCOUNT_PATTERN.search(query):
                return PIIDetectionResult(
                    has_pii=True,
                    pii_type="Account Number",
                    reason="Account number detected in query"
                )

        # No PII detected
        return PIIDetectionResult(
            has_pii=False,
            pii_type="",
            reason="No PII detected"
        )


# Pre-configured refusal response
PII_REFUSAL = (
    "For your privacy and security, please do not share personal information "
    "such as PAN, Aadhaar, account numbers, OTPs, email, or phone numbers. "
    "I can only answer factual questions about mutual fund schemes."
)
