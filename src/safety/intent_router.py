"""
Intent Router — Phase 7.1

Classifies user queries as Factual, Advisory, or Out-of-scope before retrieval.
Per §7.1: rule-based detection patterns for advisory/comparative queries.

Detection patterns:
- "should I", "which is better", "best fund", "recommend"
- Implicit ranking, personal situation ("I am 45…")
"""

import re
from dataclasses import dataclass
from enum import Enum


class QueryIntent(Enum):
    """Classification of user query intent."""
    FACTUAL = "factual"      # Proceed to retrieval
    ADVISORY = "advisory"    # Polite refusal + educational link
    OUT_OF_SCOPE = "out_of_scope"  # Out-of-scope response + educational link


@dataclass
class RouterResult:
    """Result of intent classification."""
    intent: QueryIntent
    reason: str = ""
    confidence: float = 1.0  # 0.0 to 1.0


class IntentRouter:
    """Rule-based intent classifier for FAQ queries.

    Detects advisory/comparative patterns and routes to refusal
    instead of retrieval per §7.1.
    """

    # Advisory/comparative patterns (§7.1)
    _ADVISORY_PATTERNS = [
        r"\bshould i\b",
        r"\bwhich is better\b",
        r"\bbest fund\b",
        r"\brecommend\b",
        r"\bwould you recommend\b",
        r"\bi would recommend\b",
        r"\bsuggest\b",
        r"\badvice\b",
        r"\btop fund\b",
        r"\bhighest return",
        r"\bgood investment\b",
        r"\bbad investment\b",
        r"\bworth investing\b",
        r"\bshould i invest\b",
        r"\bshould i buy\b",
        r"\boutperform\b",
        r"\bunderperform\b",
        r"\bsuperior\b",
        r"\binferior\b",
    ]

    # Personal situation patterns (implicit advisory)
    _PERSONAL_SITUATION_PATTERNS = [
        r"\bi am \d+\s*(years old|yrs? old)\b",
        r"\bmy age is\b",
        r"\bretiring in\b",
        r"\bretirement planning\b",
        r"\bmy risk appetite\b",
        r"\bmy financial goal\b",
        r"\bfor my child\b",
        r"\bfor my family\b",
    ]

    # Comparison patterns
    _COMPARISON_PATTERNS = [
        r"\bvs\b",
        r"\bversus\b",
        r"\bor\b.*\bor\b",  # "fund A or fund B or fund C"
        r"\bbetween\b.*\band\b",
        r"\bcompare\b",
    ]

    # Out-of-scope topics
    _OUT_OF_SCOPE_PATTERNS = [
        r"\bstock\b",
        r"\bshare\b",
        r"\btrading\b",
        r"\bday trading\b",
        r"\bintraday\b",
        r"\bbitcoin\b",
        r"\bcrypto\b",
        r"\bcryptocurrency\b",
        r"\breal estate\b",
        r"\bgold\b",
        r"\bproperty\b",
        r"\bloan\b",
        r"\bemi\b",
        r"\bcredit card\b",
        r"\bbank account\b",
    ]

    def __init__(self):
        """Compile regex patterns for efficiency."""
        self._advisory_regex = [re.compile(p, re.IGNORECASE) for p in self._ADVISORY_PATTERNS]
        self._personal_regex = [re.compile(p, re.IGNORECASE) for p in self._PERSONAL_SITUATION_PATTERNS]
        self._comparison_regex = [re.compile(p, re.IGNORECASE) for p in self._COMPARISON_PATTERNS]
        self._out_of_scope_regex = [re.compile(p, re.IGNORECASE) for p in self._OUT_OF_SCOPE_PATTERNS]

    def classify(self, query: str) -> RouterResult:
        """Classify query intent.

        Args:
            query: User's input query.

        Returns:
            RouterResult with intent classification and reason.
        """
        query_lower = query.lower().strip()

        # Check for out-of-scope topics first
        for pattern in self._out_of_scope_regex:
            if pattern.search(query):
                return RouterResult(
                    intent=QueryIntent.OUT_OF_SCOPE,
                    reason=f"Out-of-scope topic detected: '{pattern.pattern}'",
                    confidence=0.9
                )

        # Check for personal situation (implicit advisory)
        for pattern in self._personal_regex:
            if pattern.search(query):
                return RouterResult(
                    intent=QueryIntent.ADVISORY,
                    reason=f"Personal situation detected: '{pattern.pattern}'",
                    confidence=0.85
                )

        # Check for advisory patterns
        for pattern in self._advisory_regex:
            if pattern.search(query):
                return RouterResult(
                    intent=QueryIntent.ADVISORY,
                    reason=f"Advisory pattern detected: '{pattern.pattern}'",
                    confidence=0.9
                )

        # Check for comparison patterns (may be advisory)
        comparison_count = sum(1 for pattern in self._comparison_regex if pattern.search(query))
        if comparison_count >= 2:
            return RouterResult(
                intent=QueryIntent.ADVISORY,
                reason="Multiple comparison patterns detected",
                confidence=0.75
            )

        # Default to factual
        return RouterResult(
            intent=QueryIntent.FACTUAL,
            reason="No advisory or out-of-scope patterns detected",
            confidence=0.8
        )


# Pre-configured refusal responses
ADVISORY_REFUSAL = (
    "I cannot provide investment advice or recommendations. "
    "For educational information on mutual funds, please visit: https://www.amfiindia.com"
)

OUT_OF_SCOPE_REFUSAL = (
    "This question is outside the scope of mutual fund FAQs. "
    "For general financial education, please visit: https://www.sebi.gov.in"
)
