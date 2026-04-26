"""
Context Manager — Phase 8.2

Implements context window policy for multi-thread conversations.
Per §8.2: Use last N turns (e.g., 4–6) for follow-ups; optional query expansion.
"""

from dataclasses import dataclass
from typing import Optional

from src.threads.thread_store import Message, MessageRole, ThreadStore


@dataclass
class ConversationTurn:
    """A single turn in the conversation (user message + optional assistant response)."""
    user_message: Message
    assistant_message: Optional[Message] = None


class ContextManager:
    """Manages conversation context with sliding window policy.

    Per §8.2:
    - For factual FAQ, full thread history is often unnecessary
    - Use last N turns (e.g., 4–6) for follow-ups
    - Optional query expansion using recent history
    """

    DEFAULT_TURNS = 6  # Number of turns to keep in context

    def __init__(self, thread_store: ThreadStore, max_turns: int = DEFAULT_TURNS):
        """Initialize the context manager.

        Args:
            thread_store: ThreadStore instance for accessing messages.
            max_turns: Maximum number of turns to include in context (default: 6).
        """
        self.thread_store = thread_store
        self.max_turns = max_turns

    def get_recent_context(self, thread_id: str) -> list[ConversationTurn]:
        """Get the last N turns from a thread.

        Args:
            thread_id: Thread UUID.

        Returns:
            List of ConversationTurn objects, most recent last.
        """
        # Get last 2 * max_turns messages (user + assistant pairs)
        messages = self.thread_store.get_messages(
            thread_id,
            limit=2 * self.max_turns
        )

        # Group into turns
        turns = []
        current_turn = None

        for msg in messages:
            if msg.role == MessageRole.USER:
                # Start a new turn
                if current_turn:
                    turns.append(current_turn)
                current_turn = ConversationTurn(user_message=msg)
            elif msg.role == MessageRole.ASSISTANT:
                # Complete the current turn
                if current_turn:
                    current_turn.assistant_message = msg
                    turns.append(current_turn)
                    current_turn = None

        # Add incomplete turn if exists
        if current_turn:
            turns.append(current_turn)

        # Keep only the last max_turns
        if len(turns) > self.max_turns:
            turns = turns[-self.max_turns:]

        return turns

    def expand_query(
        self,
        thread_id: str,
        current_query: str,
        max_history_turns: int = 2
    ) -> str:
        """Optionally expand the current query using recent conversation history.

        Per §8.2: Rewrite latest user message using recent history
        (e.g., "same scheme as before") without injecting PII.

        Args:
            thread_id: Thread UUID.
            current_query: The current user query.
            max_history_turns: Number of recent turns to consider for expansion.

        Returns:
            Expanded query string (or original if no expansion needed).
        """
        recent_turns = self.get_recent_context(thread_id)

        if not recent_turns:
            return current_query

        # Get the last few turns for context
        context_turns = recent_turns[-max_history_turns:] if len(recent_turns) > max_history_turns else recent_turns

        # Simple heuristic: if current query is short and refers to "it", "that", "this", etc.
        # prepend the last user message for context
        pronouns = ["it", "that", "this", "the fund", "the scheme"]
        query_lower = current_query.lower()

        # Check if query contains pronouns or is very short
        needs_expansion = (
            any(pronoun in query_lower for pronoun in pronouns) or
            len(current_query.split()) < 5
        )

        if needs_expansion and context_turns:
            # Get the last user message for context
            last_user_msg = context_turns[-1].user_message.content
            # Prepend context to query
            expanded = f"Context: {last_user_msg}\nCurrent question: {current_query}"
            return expanded

        return current_query

    def get_conversation_summary(self, thread_id: str) -> str:
        """Get a brief summary of the conversation for debugging.

        Args:
            thread_id: Thread UUID.

        Returns:
            String summary of the conversation.
        """
        turns = self.get_recent_context(thread_id)
        if not turns:
            return "No conversation history."

        summary_parts = []
        for i, turn in enumerate(turns, 1):
            summary_parts.append(f"Turn {i}:")
            summary_parts.append(f"  User: {turn.user_message.content[:100]}...")
            if turn.assistant_message:
                summary_parts.append(f"  Assistant: {turn.assistant_message.content[:100]}...")

        return "\n".join(summary_parts)
