"""
Tests for orchestrator.process_query.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from utils.logging import setup_logging
from core.database import Base

# In-memory SQLite engine for testing
test_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
)

TestSessionLocal = sessionmaker(
    test_engine,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_logging_fixture():
    """Initialize logging for tests."""
    setup_logging()


@pytest.fixture(autouse=True)
def setup_database():
    """Set up in-memory database for each test."""
    # Create tables using test engine
    with test_engine.begin() as conn:
        Base.metadata.create_all(conn)

    yield

    # Cleanup - drop all tables after each test
    with test_engine.begin() as conn:
        Base.metadata.drop_all(conn)


class TestProcessQuery:
    """Test cases for orchestrator.process_query."""

    @pytest.mark.asyncio
    async def test_process_query_returns_expected_structure(self):
        """Test that process_query returns a dict with expected keys."""
        from core.orchestrator import process_query

        # Mock the external dependencies to avoid real API calls
        with patch("core.orchestrator.get_classifier") as mock_get_classifier, \
             patch("core.orchestrator.get_retriever") as mock_get_retriever, \
             patch("core.orchestrator.get_doc_store") as mock_get_doc_store, \
             patch("core.orchestrator._generate_rag_response") as mock_generate:

            # Setup mocks
            mock_classifier = MagicMock()
            mock_classifier.classify = AsyncMock(return_value={
                "intent_id": 1,
                "intent_name": "General",
                "confidence": 0.9
            })
            mock_get_classifier.return_value = mock_classifier

            mock_doc_store = MagicMock()
            mock_doc_store.get_query_embedding = AsyncMock(return_value=[])
            mock_get_doc_store.return_value = mock_doc_store

            mock_retriever = MagicMock()
            mock_retriever.retrieve = AsyncMock(return_value=[
                {"chunk_id": "1_0", "content": "test content", "document_id": 1}
            ])
            mock_get_retriever.return_value = mock_retriever

            mock_generate.return_value = "This is a test response"

            # Call process_query
            result = process_query(
                query_text="test query",
                source="telegram",
                chat_id="user123"
            )

            # Verify return structure
            assert isinstance(result, dict)
            assert "response" in result
            assert "intent_id" in result
            assert "intent_name" in result
            assert "confidence" in result
            assert "document_id" in result
            assert "response_time_ms" in result

            # Verify types
            assert isinstance(result["response"], str)
            assert isinstance(result["intent_id"], int)
            assert isinstance(result["intent_name"], str)
            assert isinstance(result["confidence"], float)
            assert isinstance(result["response_time_ms"], int)

    @pytest.mark.asyncio
    async def test_process_query_invalid_source_raises_error(self):
        """Test that invalid source raises ValueError."""
        from core.orchestrator import process_query

        with pytest.raises(ValueError, match="Invalid source"):
            process_query(
                query_text="test query",
                source="invalid_source",
                chat_id="user123"
            )

    @pytest.mark.asyncio
    async def test_process_query_with_empty_results(self):
        """Test process_query handles empty retrieval results."""
        from core.orchestrator import process_query

        with patch("core.orchestrator.get_classifier") as mock_get_classifier, \
             patch("core.orchestrator.get_retriever") as mock_get_retriever, \
             patch("core.orchestrator.get_doc_store") as mock_get_doc_store, \
             patch("core.orchestrator._generate_rag_response") as mock_generate:

            # Setup mocks with empty results
            mock_classifier = MagicMock()
            mock_classifier.classify = AsyncMock(return_value={
                "intent_id": None,
                "intent_name": "General",
                "confidence": 0.0
            })
            mock_get_classifier.return_value = mock_classifier

            mock_doc_store = MagicMock()
            mock_doc_store.get_query_embedding = AsyncMock(return_value=[])
            mock_get_doc_store.return_value = mock_doc_store

            mock_retriever = MagicMock()
            mock_retriever.retrieve = AsyncMock(return_value=[])
            mock_get_retriever.return_value = mock_retriever

            mock_generate.return_value = "No relevant documents found."

            # Call process_query
            result = process_query(
                query_text="test query",
                source="teams",
                chat_id="channel456"
            )

            # Verify empty results are handled
            assert result["response"] == "No relevant documents found."
            assert result["document_id"] is None

    @pytest.mark.asyncio
    async def test_process_query_logs_to_database(self):
        """Test that process_query creates a QueryLog entry."""
        from core.orchestrator import process_query
        from models import QueryLog
        from sqlalchemy import select

        with patch("core.database.SessionLocal", new=TestSessionLocal), \
             patch("core.orchestrator.get_classifier") as mock_get_classifier, \
             patch("core.orchestrator.get_retriever") as mock_get_retriever, \
             patch("core.orchestrator.get_doc_store") as mock_get_doc_store, \
             patch("core.orchestrator._generate_rag_response") as mock_generate:

            mock_classifier = MagicMock()
            mock_classifier.classify = AsyncMock(return_value={
                "intent_id": 1,
                "intent_name": "General",
                "confidence": 0.9
            })
            mock_get_classifier.return_value = mock_classifier

            mock_doc_store = MagicMock()
            mock_doc_store.get_query_embedding = AsyncMock(return_value=[])
            mock_get_doc_store.return_value = mock_doc_store

            mock_retriever = MagicMock()
            mock_retriever.retrieve = AsyncMock(return_value=[])
            mock_get_retriever.return_value = mock_retriever

            mock_generate.return_value = "Test response"

            # Call process_query
            process_query(
                query_text="log test query",
                source="telegram",
                chat_id="user789"
            )

            # Verify QueryLog was created
            with TestSessionLocal() as db:
                result = db.execute(
                    select(QueryLog).where(QueryLog.query_text == "log test query")
                )
                log = result.scalar_one_or_none()

                assert log is not None
                assert log.source == "telegram"
                assert log.user_id == "user789"
                assert log.response_text == "Test response"
