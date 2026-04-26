"""
Phase 6 — Generation Layer public API.

    from src.generation import Generator, GenerationResult

See docs/rag_architecture.md §6 for design rationale.
"""

from src.generation.generator import GenerationResult, Generator
from src.generation.prompt_builder import ALLOWLISTED_URLS, build_user_turn
from src.generation.validator import ResponseValidator, ValidationResult

__all__ = [
    "Generator",
    "GenerationResult",
    "ResponseValidator",
    "ValidationResult",
    "ALLOWLISTED_URLS",
    "build_user_turn",
]
