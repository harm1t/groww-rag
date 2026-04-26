"""
Phase 9 — Application & API Layer

Import from here rather than directly from sub-modules:

    from src.api import app

See docs/rag_architecture.md §9 for design rationale.
"""

from src.api.app import app

__all__ = ["app"]
