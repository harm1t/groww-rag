"""
Phase 7 — Safety & Refusal Layer

Import from here rather than directly from sub-modules:

    from src.safety import (
        IntentRouter,
        QueryIntent,
        RouterResult,
        PIIDetector,
        PIIDetectionResult,
        SafetyOrchestrator,
        SafetyResult,
        ADVISORY_REFUSAL,
        OUT_OF_SCOPE_REFUSAL,
        PII_REFUSAL,
    )

See docs/rag_architecture.md §7 for design rationale.
"""

from src.safety.intent_router import (
    ADVISORY_REFUSAL,
    IntentRouter,
    OUT_OF_SCOPE_REFUSAL,
    QueryIntent,
    RouterResult,
)
from src.safety.orchestrator import SafetyOrchestrator, SafetyResult
from src.safety.pii_detector import PIIDetector, PIIDetectionResult, PII_REFUSAL

__all__ = [
    "IntentRouter",
    "QueryIntent",
    "RouterResult",
    "PIIDetector",
    "PIIDetectionResult",
    "SafetyOrchestrator",
    "SafetyResult",
    "ADVISORY_REFUSAL",
    "OUT_OF_SCOPE_REFUSAL",
    "PII_REFUSAL",
]
