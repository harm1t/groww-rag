"""
Tests for Phase 8 — Multi-Thread Chat Architecture

Tests:
- Thread store (SQLite CRUD operations)
- Message storage and retrieval
- Context window policy (last N turns)
- Query expansion
"""

import pytest
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.threads import (
    ContextManager,
    ConversationTurn,
    Message,
    MessageRole,
    Thread,
    ThreadStore,
)


class TestThreadStore:
    """Test the ThreadStore class."""

    def test_create_thread(self):
        """Test creating a new thread with UUID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            assert thread.id is not None
            assert len(thread.id) == 36  # UUID format
            assert thread.message_count == 0
            assert thread.created_at is not None
            assert thread.updated_at is not None

    def test_get_thread(self):
        """Test retrieving a thread by ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            created = store.create_thread()
            retrieved = store.get_thread(created.id)

            assert retrieved is not None
            assert retrieved.id == created.id
            assert retrieved.created_at == created.created_at

    def test_get_nonexistent_thread(self):
        """Test retrieving a non-existent thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            result = store.get_thread("nonexistent-id")
            assert result is None

    def test_list_threads(self):
        """Test listing threads, most recently updated first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))

            thread1 = store.create_thread()
            thread2 = store.create_thread()
            thread3 = store.create_thread()

            threads = store.list_threads(limit=10)

            assert len(threads) == 3
            # Most recently created should be first
            assert threads[0].id == thread3.id
            assert threads[1].id == thread2.id
            assert threads[2].id == thread1.id

    def test_list_threads_with_limit(self):
        """Test listing threads with a limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))

            for _ in range(5):
                store.create_thread()

            threads = store.list_threads(limit=3)
            assert len(threads) == 3

    def test_delete_thread(self):
        """Test deleting a thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            result = store.delete_thread(thread.id)
            assert result is True

            # Thread should no longer exist
            assert store.get_thread(thread.id) is None

    def test_delete_nonexistent_thread(self):
        """Test deleting a non-existent thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            result = store.delete_thread("nonexistent-id")
            assert result is False


class TestMessageStorage:
    """Test message storage and retrieval."""

    def test_add_user_message(self):
        """Test adding a user message to a thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            message = store.add_message(
                thread_id=thread.id,
                role=MessageRole.USER,
                content="What is the NAV?"
            )

            assert message.id is not None
            assert message.thread_id == thread.id
            assert message.role == MessageRole.USER
            assert message.content == "What is the NAV?"
            assert message.timestamp is not None

    def test_add_assistant_message(self):
        """Test adding an assistant message to a thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            message = store.add_message(
                thread_id=thread.id,
                role=MessageRole.ASSISTANT,
                content="The NAV is 45.67",
                retrieval_debug_id="debug-123"
            )

            assert message.role == MessageRole.ASSISTANT
            assert message.retrieval_debug_id == "debug-123"

    def test_add_message_to_nonexistent_thread(self):
        """Test adding a message to a non-existent thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))

            with pytest.raises(ValueError, match="not found"):
                store.add_message(
                    thread_id="nonexistent-id",
                    role=MessageRole.USER,
                    content="Test"
                )

    def test_get_messages_chronological(self):
        """Test retrieving messages in chronological order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            msg1 = store.add_message(thread.id, MessageRole.USER, "First question")
            msg2 = store.add_message(thread.id, MessageRole.ASSISTANT, "First answer")
            msg3 = store.add_message(thread.id, MessageRole.USER, "Second question")

            messages = store.get_messages(thread.id)

            assert len(messages) == 3
            assert messages[0].id == msg1.id
            assert messages[1].id == msg2.id
            assert messages[2].id == msg3.id

    def test_get_messages_with_limit(self):
        """Test retrieving messages with a limit (most recent first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            for i in range(5):
                store.add_message(thread.id, MessageRole.USER, f"Message {i}")

            messages = store.get_messages(thread.id, limit=2)

            assert len(messages) == 2
            # Should get the last 2 messages
            assert "Message 3" in messages[0].content
            assert "Message 4" in messages[1].content

    def test_thread_message_count(self):
        """Test that thread message count is accurate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            assert thread.message_count == 0

            store.add_message(thread.id, MessageRole.USER, "Question 1")
            store.add_message(thread.id, MessageRole.ASSISTANT, "Answer 1")

            updated_thread = store.get_thread(thread.id)
            assert updated_thread.message_count == 2

    def test_thread_updated_at_timestamp(self):
        """Test that thread updated_at changes when messages are added."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            original_updated = thread.updated_at

            # Add a message
            store.add_message(thread.id, MessageRole.USER, "Test")

            updated_thread = store.get_thread(thread.id)
            assert updated_thread.updated_at > original_updated


class TestContextManager:
    """Test the ContextManager class."""

    def test_get_recent_context_empty(self):
        """Test getting context from an empty thread."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()
            ctx_mgr = ContextManager(store)

            context = ctx_mgr.get_recent_context(thread.id)
            assert context == []

    def test_get_recent_context_single_turn(self):
        """Test getting context with one turn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()
            ctx_mgr = ContextManager(store)

            store.add_message(thread.id, MessageRole.USER, "What is NAV?")
            store.add_message(thread.id, MessageRole.ASSISTANT, "NAV is 45.67")

            context = ctx_mgr.get_recent_context(thread.id)

            assert len(context) == 1
            assert context[0].user_message.content == "What is NAV?"
            assert context[0].assistant_message.content == "NAV is 45.67"

    def test_get_recent_context_multiple_turns(self):
        """Test getting context with multiple turns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()
            ctx_mgr = ContextManager(store, max_turns=3)

            # Add 3 complete turns
            for i in range(3):
                store.add_message(thread.id, MessageRole.USER, f"Question {i}")
                store.add_message(thread.id, MessageRole.ASSISTANT, f"Answer {i}")

            context = ctx_mgr.get_recent_context(thread.id)

            assert len(context) == 3
            assert context[0].user_message.content == "Question 0"
            assert context[2].user_message.content == "Question 2"

    def test_get_recent_context_respects_max_turns(self):
        """Test that context manager respects max_turns limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()
            ctx_mgr = ContextManager(store, max_turns=2)

            # Add 5 turns
            for i in range(5):
                store.add_message(thread.id, MessageRole.USER, f"Question {i}")
                store.add_message(thread.id, MessageRole.ASSISTANT, f"Answer {i}")

            context = ctx_mgr.get_recent_context(thread.id)

            # Should only return last 2 turns
            assert len(context) == 2
            assert context[0].user_message.content == "Question 3"
            assert context[1].user_message.content == "Question 4"

    def test_expand_query_with_pronoun(self):
        """Test query expansion when query contains pronoun."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()
            ctx_mgr = ContextManager(store)

            # Add previous context
            store.add_message(thread.id, MessageRole.USER, "What is Parag Parikh Flexi Cap Fund?")
            store.add_message(thread.id, MessageRole.ASSISTANT, "It's a flexi cap fund...")

            # Query with pronoun
            expanded = ctx_mgr.expand_query(thread.id, "What is its NAV?")

            assert "Context:" in expanded
            assert "Parag Parikh Flexi Cap Fund" in expanded
            assert "What is its NAV?" in expanded

    def test_expand_query_short_query(self):
        """Test query expansion for short queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()
            ctx_mgr = ContextManager(store)

            store.add_message(thread.id, MessageRole.USER, "Tell me about Parag Parikh funds")

            expanded = ctx_mgr.expand_query(thread.id, "NAV?")

            assert "Context:" in expanded
            assert "Parag Parikh funds" in expanded

    def test_expand_query_no_expansion_needed(self):
        """Test that detailed queries are not expanded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()
            ctx_mgr = ContextManager(store)

            store.add_message(thread.id, MessageRole.USER, "Previous question")

            # Detailed query - no expansion needed
            expanded = ctx_mgr.expand_query(
                thread.id,
                "What is the NAV of Parag Parikh Flexi Cap Fund as of today?"
            )

            # Should return original query
            assert expanded == "What is the NAV of Parag Parikh Flexi Cap Fund as of today?"

    def test_get_conversation_summary(self):
        """Test getting a conversation summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()
            ctx_mgr = ContextManager(store)

            store.add_message(thread.id, MessageRole.USER, "What is NAV?")
            store.add_message(thread.id, MessageRole.ASSISTANT, "NAV is 45.67")

            summary = ctx_mgr.get_conversation_summary(thread.id)

            assert "Turn 1" in summary
            assert "User: What is NAV?" in summary
            assert "Assistant: NAV is 45.67" in summary


class TestConcurrentAccess:
    """Test concurrent access to multiple threads."""

    def test_concurrent_thread_creation(self):
        """Test creating multiple threads concurrently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))

            def create_and_add_messages():
                thread = store.create_thread()
                for i in range(3):
                    store.add_message(thread.id, MessageRole.USER, f"Message {i}")
                    store.add_message(thread.id, MessageRole.ASSISTANT, f"Response {i}")
                return thread.id

            # Create 10 threads concurrently
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(create_and_add_messages) for _ in range(10)]
                thread_ids = [f.result() for f in as_completed(futures)]

            # Verify all threads were created and are unique
            assert len(thread_ids) == 10
            assert len(set(thread_ids)) == 10

            # Verify each thread has 6 messages
            for thread_id in thread_ids:
                thread = store.get_thread(thread_id)
                assert thread.message_count == 6
                messages = store.get_messages(thread_id)
                assert len(messages) == 6

    def test_concurrent_message_addition_to_same_thread(self):
        """Test adding messages to the same thread from multiple workers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread = store.create_thread()

            def add_message(worker_id):
                store.add_message(
                    thread.id,
                    MessageRole.USER,
                    f"Message from worker {worker_id}"
                )

            # Add 20 messages concurrently from different workers
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(add_message, i) for i in range(20)]
                for f in as_completed(futures):
                    f.result()

            # Verify all messages were added
            thread = store.get_thread(thread.id)
            assert thread.message_count == 20

    def test_concurrent_thread_isolation(self):
        """Test that concurrent operations on different threads don't interfere."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = ThreadStore(str(db_path))
            thread1 = store.create_thread()
            thread2 = store.create_thread()

            def add_messages_to_thread(thread_id, prefix):
                for i in range(5):
                    store.add_message(
                        thread_id,
                        MessageRole.USER,
                        f"{prefix} message {i}"
                    )

            # Add messages to both threads concurrently
            with ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(add_messages_to_thread, thread1.id, "Thread1")
                future2 = executor.submit(add_messages_to_thread, thread2.id, "Thread2")
                future1.result()
                future2.result()

            # Verify isolation: each thread has only its own messages
            messages1 = store.get_messages(thread1.id)
            messages2 = store.get_messages(thread2.id)

            assert len(messages1) == 5
            assert len(messages2) == 5

            # Check that Thread1 messages don't contain Thread2 prefix
            for msg in messages1:
                assert "Thread1" in msg.content
                assert "Thread2" not in msg.content

            # Check that Thread2 messages don't contain Thread1 prefix
            for msg in messages2:
                assert "Thread2" in msg.content
                assert "Thread1" not in msg.content
