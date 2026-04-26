"""
Thread Store — Phase 8.1

SQLite-based storage for threads and messages.
Per §8.1: Thread ID (UUID), Message schema { role, content, timestamp, optional retrieval_debug_id }.
"""

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class MessageRole(Enum):
    """Role of a message in a conversation."""
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """A single message in a thread."""
    id: str
    thread_id: str
    role: MessageRole
    content: str
    timestamp: str  # ISO format
    retrieval_debug_id: Optional[str] = None


@dataclass
class Thread:
    """A conversation thread."""
    id: str
    created_at: str  # ISO format
    updated_at: str  # ISO format
    message_count: int = 0


class ThreadStore:
    """SQLite-based thread and message storage.

    Schema:
    - threads: id (UUID), created_at, updated_at
    - messages: id (UUID), thread_id, role, content, timestamp, retrieval_debug_id
    """

    def __init__(self, db_path: str = "data/threads.db"):
        """Initialize the thread store.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist and enable WAL mode for concurrency."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Enable WAL mode for better concurrency (allows concurrent reads/writes)
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")  # 5 second timeout for locks
            # Threads table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    retrieval_debug_id TEXT,
                    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
                )
            """)
            # Index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_thread_id
                ON messages(thread_id, timestamp)
            """)
            conn.commit()

    def create_thread(self) -> Thread:
        """Create a new thread with a UUID.

        Returns:
            Thread object with generated UUID.
        """
        thread_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO threads (id, created_at, updated_at) VALUES (?, ?, ?)",
                (thread_id, now, now)
            )
            conn.commit()

        return Thread(id=thread_id, created_at=now, updated_at=now, message_count=0)

    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID.

        Args:
            thread_id: Thread UUID.

        Returns:
            Thread object or None if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, created_at, updated_at FROM threads WHERE id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()
            if row:
                # Get message count
                cursor.execute(
                    "SELECT COUNT(*) FROM messages WHERE thread_id = ?",
                    (thread_id,)
                )
                count = cursor.fetchone()[0]
                return Thread(id=row[0], created_at=row[1], updated_at=row[2], message_count=count)
        return None

    def list_threads(self, limit: int = 50) -> list[Thread]:
        """List all threads, most recently updated first.

        Args:
            limit: Maximum number of threads to return.

        Returns:
            List of Thread objects.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, created_at, updated_at
                FROM threads
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

            threads = []
            for row in rows:
                # Get message count for each thread
                cursor.execute(
                    "SELECT COUNT(*) FROM messages WHERE thread_id = ?",
                    (row[0],)
                )
                count = cursor.fetchone()[0]
                threads.append(Thread(id=row[0], created_at=row[1], updated_at=row[2], message_count=count))

            return threads

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread and all its messages.

        Args:
            thread_id: Thread UUID.

        Returns:
            True if deleted, False if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted

    def add_message(
        self,
        thread_id: str,
        role: MessageRole,
        content: str,
        retrieval_debug_id: Optional[str] = None
    ) -> Message:
        """Add a message to a thread.

        Args:
            thread_id: Thread UUID.
            role: Message role (user or assistant).
            content: Message content.
            retrieval_debug_id: Optional debug ID for retrieval.

        Returns:
            Message object with generated UUID.

        Raises:
            ValueError: If thread_id does not exist.
        """
        # Verify thread exists
        if not self.get_thread(thread_id):
            raise ValueError(f"Thread {thread_id} not found")

        message_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages (id, thread_id, role, content, timestamp, retrieval_debug_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, thread_id, role.value, content, now, retrieval_debug_id)
            )
            # Update thread's updated_at
            cursor.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (now, thread_id)
            )
            conn.commit()

        return Message(
            id=message_id,
            thread_id=thread_id,
            role=role,
            content=content,
            timestamp=now,
            retrieval_debug_id=retrieval_debug_id
        )

    def get_messages(self, thread_id: str, limit: Optional[int] = None) -> list[Message]:
        """Get messages from a thread, in chronological order.

        Args:
            thread_id: Thread UUID.
            limit: Optional maximum number of messages to return (most recent first if limited).

        Returns:
            List of Message objects.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if limit:
                cursor.execute(
                    """
                    SELECT id, thread_id, role, content, timestamp, retrieval_debug_id
                    FROM messages
                    WHERE thread_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (thread_id, limit)
                )
                rows = cursor.fetchall()
                # Reverse to get chronological order
                rows = rows[::-1]
            else:
                cursor.execute(
                    """
                    SELECT id, thread_id, role, content, timestamp, retrieval_debug_id
                    FROM messages
                    WHERE thread_id = ?
                    ORDER BY timestamp ASC
                    """,
                    (thread_id,)
                )
                rows = cursor.fetchall()

            return [
                Message(
                    id=row[0],
                    thread_id=row[1],
                    role=MessageRole(row[2]),
                    content=row[3],
                    timestamp=row[4],
                    retrieval_debug_id=row[5]
                )
                for row in rows
            ]
