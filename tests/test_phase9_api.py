"""
Tests for Phase 9 — Application & API Layer

Tests:
- Health check endpoint
- Thread management endpoints
- Message endpoints
- Admin reindex endpoint
"""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture
def test_db_path():
    """Provide a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_threads.db"
        yield str(db_path)


@pytest.fixture
def client(test_db_path):
    """Create a test client with temporary database."""
    # Set environment variable for test database
    os.environ["THREAD_DB_PATH"] = test_db_path
    os.environ["RUNTIME_API_DEBUG"] = "1"  # Enable debug mode for testing

    # Create test client
    with TestClient(app) as test_client:
        yield test_client

    # Cleanup
    if "THREAD_DB_PATH" in os.environ:
        del os.environ["THREAD_DB_PATH"]
    if "RUNTIME_API_DEBUG" in os.environ:
        del os.environ["RUNTIME_API_DEBUG"]


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_check(self, client):
        """Test GET /health returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestRootEndpoint:
    """Test the root endpoint."""

    def test_root_serves_ui(self, client):
        """Test GET / serves the chat UI HTML."""
        response = client.get("/")
        assert response.status_code == 200
        # Should serve HTML when the static file exists
        assert "text/html" in response.headers.get("content-type", "")
        assert "PPFAS" in response.text or "Mutual Fund" in response.text


class TestThreadEndpoints:
    """Test thread management endpoints."""

    def test_create_thread(self, client):
        """Test POST /threads creates a new thread."""
        response = client.post("/threads")
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert len(data["id"]) == 36  # UUID format
        assert "created_at" in data
        assert "updated_at" in data
        assert data["message_count"] == 0

    def test_list_threads_empty(self, client):
        """Test GET /threads with no threads."""
        response = client.get("/threads")
        assert response.status_code == 200
        data = response.json()
        assert "threads" in data
        assert len(data["threads"]) == 0

    def test_list_threads_with_data(self, client):
        """Test GET /threads returns threads in order."""
        # Create multiple threads
        thread1 = client.post("/threads").json()
        thread2 = client.post("/threads").json()
        thread3 = client.post("/threads").json()

        response = client.get("/threads")
        assert response.status_code == 200
        data = response.json()
        assert len(data["threads"]) == 3
        # Most recently created should be first
        assert data["threads"][0]["id"] == thread3["id"]
        assert data["threads"][1]["id"] == thread2["id"]
        assert data["threads"][2]["id"] == thread1["id"]

    def test_list_threads_with_limit(self, client):
        """Test GET /threads with limit parameter."""
        # Create 5 threads
        for _ in range(5):
            client.post("/threads")

        response = client.get("/threads?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["threads"]) == 3


class TestMessageEndpoints:
    """Test message endpoints."""

    def test_get_messages_empty_thread(self, client):
        """Test GET /threads/{id}/messages for empty thread."""
        thread = client.post("/threads").json()
        thread_id = thread["id"]

        response = client.get(f"/threads/{thread_id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 0

    def test_get_messages_nonexistent_thread(self, client):
        """Test GET /threads/{id}/messages for non-existent thread."""
        response = client.get("/threads/nonexistent-id/messages")
        assert response.status_code == 404

    def test_post_message(self, client):
        """Test POST /threads/{id}/messages."""
        thread = client.post("/threads").json()
        thread_id = thread["id"]

        request_data = {"content": "What is the NAV?"}
        response = client.post(f"/threads/{thread_id}/messages", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "assistant_message" in data
        # Since safety orchestrator is not initialized, expect placeholder
        assert "not fully configured" in data["assistant_message"].lower()

    def test_post_message_nonexistent_thread(self, client):
        """Test POST /threads/{id}/messages for non-existent thread."""
        request_data = {"content": "Test"}
        response = client.post("/threads/nonexistent-id/messages", json=request_data)
        assert response.status_code == 404

    def test_get_messages_after_post(self, client):
        """Test GET /threads/{id}/messages after posting."""
        thread = client.post("/threads").json()
        thread_id = thread["id"]

        # Post a message
        client.post(f"/threads/{thread_id}/messages", json={"content": "Test"})

        # Get messages
        response = client.get(f"/threads/{thread_id}/messages")
        assert response.status_code == 200
        data = response.json()
        # Should have 2 messages (user + assistant)
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"

    def test_get_messages_with_limit(self, client):
        """Test GET /threads/{id}/messages with limit."""
        thread = client.post("/threads").json()
        thread_id = thread["id"]

        # Post multiple messages
        for i in range(5):
            client.post(f"/threads/{thread_id}/messages", json={"content": f"Message {i}"})

        response = client.get(f"/threads/{thread_id}/messages?limit=4")
        assert response.status_code == 200
        data = response.json()
        # Should return last 4 messages (8 total: 5 user + 5 assistant)
        assert len(data["messages"]) == 4


class TestAdminReindexEndpoint:
    """Test admin reindex endpoint."""

    def test_reindex_no_secret_configured(self, client):
        """Test POST /admin/reindex when no secret is configured."""
        # Ensure no secret is set
        if "ADMIN_REINDEX_SECRET" in os.environ:
            del os.environ["ADMIN_REINDEX_SECRET"]

        request_data = {"secret": "any-secret"}
        response = client.post("/admin/reindex", json=request_data)
        assert response.status_code == 503
        data = response.json()
        assert "not configured" in data["detail"].lower()

    def test_reindex_invalid_secret(self, client):
        """Test POST /admin/reindex with invalid secret."""
        os.environ["ADMIN_REINDEX_SECRET"] = "correct-secret"

        request_data = {"secret": "wrong-secret"}
        response = client.post("/admin/reindex", json=request_data)
        assert response.status_code == 401
        data = response.json()
        assert "invalid" in data["detail"].lower()

        # Cleanup
        del os.environ["ADMIN_REINDEX_SECRET"]

    def test_reindex_valid_secret(self, client):
        """Test POST /admin/reindex with valid secret."""
        os.environ["ADMIN_REINDEX_SECRET"] = "test-secret"

        request_data = {"secret": "test-secret"}
        response = client.post("/admin/reindex", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "message" in data

        # Cleanup
        del os.environ["ADMIN_REINDEX_SECRET"]


class TestDebugMode:
    """Test debug mode functionality."""

    def test_debug_info_in_response(self, client):
        """Test that debug info is included when RUNTIME_API_DEBUG=1."""
        thread = client.post("/threads").json()
        thread_id = thread["id"]

        request_data = {"content": "Test"}
        response = client.post(f"/threads/{thread_id}/messages", json=request_data)
        assert response.status_code == 200
        data = response.json()

        # Debug info should be present
        assert "debug" in data
        assert data["debug"] is not None
        assert "latency_ms" in data["debug"]
