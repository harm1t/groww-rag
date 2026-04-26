"""
Safety Orchestrator — Phase 7

Orchestrates the full query pipeline: PII detection → Intent routing → 
Retrieval (Phase 5) → Generation (Phase 6) → Post-validation.

Per §7: rule-based router before retrieval, templated refusal, 
PII heuristics + log redaction, answer() orchestrating phases 5→6.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.generation import Generator, GenerationResult
from src.retrieval import Retriever, RetrievalResult
from src.safety.intent_router import (
    ADVISORY_REFUSAL,
    IntentRouter,
    OUT_OF_SCOPE_REFUSAL,
    QueryIntent,
    RouterResult,
)
from src.safety.pii_detector import PIIDetector, PIIDetectionResult, PII_REFUSAL

logger = logging.getLogger(__name__)


@dataclass
class SafetyResult:
    """Result of the full safety-orchestrated pipeline."""
    response: str
    router_result: Optional[RouterResult] = None
    pii_result: Optional[PIIDetectionResult] = None
    retrieval_result: Optional[RetrievalResult] = None
    generation_result: Optional[GenerationResult] = None
    was_refused: bool = False
    refusal_reason: str = ""


class SafetyOrchestrator:
    """Orchestrates the full query pipeline with safety checks.

    Pipeline:
    1. PII detection → reject if found
    2. Intent routing → factual vs advisory vs out-of-scope
    3. If factual: Retrieval (Phase 5) → Generation (Phase 6) → Validation
    4. If advisory/out-of-scope: templated refusal
    """

    def __init__(
        self,
        retriever: Retriever,
        generator: Generator,
        pii_detector: Optional[PIIDetector] = None,
        intent_router: Optional[IntentRouter] = None,
    ):
        """Initialize the safety orchestrator.

        Args:
            retriever: Phase 5 retriever instance.
            generator: Phase 6 generator instance.
            pii_detector: PII detector (default: new instance).
            intent_router: Intent router (default: new instance).
        """
        self.retriever = retriever
        self.generator = generator
        self.pii_detector = pii_detector or PIIDetector()
        self.intent_router = intent_router or IntentRouter()

    def answer(self, query: str, conversation_history: Optional[list[str]] = None, top_k: int = 20) -> SafetyResult:
        """Process a user query through the full safety pipeline.

        Args:
            query: User's input query.
            conversation_history: Optional list of previous messages in the conversation (for context).
            top_k: Number of chunks to retrieve (default: 20).

        Returns:
            SafetyResult with the response and metadata.
        """
        # Step 1: Expand query with conversation context if provided
        expanded_query = self._expand_query_with_context(query, conversation_history)
        
        # Step 2: PII detection (§7.3) - use original query for PII check
        pii_result = self.pii_detector.detect(query)
        if pii_result.has_pii:
            logger.warning("[PII] %s - Query: %s", pii_result.reason, self._redact_query(query))
            return SafetyResult(
                response=PII_REFUSAL,
                pii_result=pii_result,
                was_refused=True,
                refusal_reason=f"PII detected: {pii_result.pii_type}",
            )

        # Step 3: Intent routing (§7.1) - use original query for routing
        router_result = self.intent_router.classify(query)
        logger.info(
            "[Router] Intent: %s, Confidence: %.2f, Reason: %s",
            router_result.intent.value,
            router_result.confidence,
            router_result.reason,
        )

        if router_result.intent == QueryIntent.ADVISORY:
            return SafetyResult(
                response=ADVISORY_REFUSAL,
                router_result=router_result,
                pii_result=pii_result,
                was_refused=True,
                refusal_reason="Advisory query detected",
            )

        if router_result.intent == QueryIntent.OUT_OF_SCOPE:
            return SafetyResult(
                response=OUT_OF_SCOPE_REFUSAL,
                router_result=router_result,
                pii_result=pii_result,
                was_refused=True,
                refusal_reason="Out-of-scope query detected",
            )

        # Step 4: Retrieval (Phase 5) - use expanded query for retrieval
        try:
            retrieval_result = self.retriever.retrieve(expanded_query)
            logger.info(
                "[Retrieval] Retrieved %d chunks from %d sources",
                retrieval_result.chunks_retrieved,
                retrieval_result.sources_merged,
            )
        except Exception as e:
            logger.error("[Retrieval] Failed: %s", str(e))
            return SafetyResult(
                response="I encountered an error while retrieving information. Please try again later.",
                router_result=router_result,
                pii_result=pii_result,
                was_refused=True,
                refusal_reason=f"Retrieval error: {str(e)}",
            )

        # Step 5: Generation (Phase 6) - use expanded query for generation
        try:
            generation_result = self.generator.generate(expanded_query, retrieval_result)
            logger.info(
                "[Generation] Generated response (validated: %s, retries: %d)",
                generation_result.validation.passed,
                generation_result.retry_used,
            )
        except Exception as e:
            logger.error("[Generation] Failed: %s", str(e))
            return SafetyResult(
                response="I encountered an error while generating a response. Please try again later.",
                router_result=router_result,
                pii_result=pii_result,
                retrieval_result=retrieval_result,
                was_refused=True,
                refusal_reason=f"Generation error: {str(e)}",
            )

        return SafetyResult(
            response=generation_result.answer_text,
            router_result=router_result,
            pii_result=pii_result,
            retrieval_result=retrieval_result,
            generation_result=generation_result,
            was_refused=False,
            refusal_reason="",
        )

    def _expand_query_with_context(self, query: str, conversation_history: Optional[list[str]] = None) -> str:
        """Expand the query with conversation context if needed.

        Args:
            query: Current user query.
            conversation_history: List of previous messages in the conversation.

        Returns:
            Expanded query or original query if no expansion needed.
        """
        if not conversation_history:
            return query

        # Get the last few messages for context (last 4 messages = 2 turns)
        recent_history = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history

        # Check if query contains pronouns or is very short (indicates follow-up)
        pronouns = ["it", "that", "this", "the fund", "the scheme", "its", "their"]
        query_lower = query.lower()
        needs_expansion = (
            any(pronoun in query_lower for pronoun in pronouns) or
            len(query.split()) < 5
        )

        if needs_expansion and recent_history:
            # Build context from recent messages
            context_messages = []
            for msg in recent_history:
                context_messages.append(msg)
            
            # Prepend context to query
            context_str = " ".join(context_messages)
            expanded = f"Context: {context_str}\nCurrent question: {query}"
            logger.info("[Context] Expanded query with conversation history")
            return expanded

        return query

    def _redact_query(self, query: str) -> str:
        """Redact potential PII from query for logging.

        Args:
            query: Original query.

        Returns:
            Query with potential PII redacted.
        """
        # Redact long digit sequences (potential account numbers, Aadhaar, phone)
        redacted = re.sub(r"\b\d{8,}\b", "[REDACTED]", query)
        # Redact email patterns
        redacted = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", redacted, flags=re.IGNORECASE)
        # Redact PAN-like patterns
        redacted = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", "[PAN]", redacted, flags=re.IGNORECASE)
        return redacted


# Import re for redaction
import re
