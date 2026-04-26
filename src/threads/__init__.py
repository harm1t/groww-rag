"""
Phase 8 — Multi-Thread Chat Architecture

Import from here rather than directly from sub-modules:

    from src.threads import (
        ThreadStore,
        Thread,
        Message,
        MessageRole,
        ContextManager,
        ConversationTurn,
    )

See docs/rag_architecture.md §8 for design rationale.
"""

from src.threads.context_manager import ContextManager, ConversationTurn
from src.threads.thread_store import Message, MessageRole, Thread, ThreadStore

__all__ = [
    "ThreadStore",
    "Thread",
    "Message",
    "MessageRole",
    "ContextManager",
    "ConversationTurn",
]
