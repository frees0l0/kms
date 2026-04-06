"""
SQLAlchemy ORM models for IntelliKnow KMS.
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.database import Base


class Document(Base):
    """Uploaded document metadata."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(20))  # pdf, docx
    size_bytes: Mapped[int] = mapped_column(Integer)
    upload_time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processed, error
    intent_space_id: Mapped[Optional[int]] = mapped_column(ForeignKey("intent_spaces.id"), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    intent_space: Mapped[Optional["IntentSpace"]] = relationship("IntentSpace", back_populates="documents")
    chunks: Mapped[List["Chunk"]] = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    query_logs: Mapped[List["QueryLog"]] = relationship("QueryLog", back_populates="document")


class Chunk(Base):
    """Document chunks for retrieval."""
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    content: Mapped[str] = mapped_column(Text)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # e.g., {"page": 1}

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class IntentSpace(Base):
    """Intent classification spaces (HR, Legal, Finance, etc.)."""
    __tablename__ = "intent_spaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated keywords
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="intent_space")
    query_logs: Mapped[List["QueryLog"]] = relationship("QueryLog", foreign_keys="[QueryLog.intent_id]", back_populates="intent_space")


class QueryLog(Base):
    """Query history with classification results."""
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(20))  # telegram, teams, web_admin
    user_id: Mapped[str] = mapped_column(String(100))
    query_text: Mapped[str] = mapped_column(Text)
    intent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("intent_spaces.id"), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_feedback: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # correct, wrong, null
    corrected_intent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("intent_spaces.id"), nullable=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"), nullable=True)

    # Relationships
    intent_space: Mapped[Optional["IntentSpace"]] = relationship("IntentSpace", foreign_keys=[intent_id], back_populates="query_logs")
    corrected_intent: Mapped[Optional["IntentSpace"]] = relationship("IntentSpace", foreign_keys=[corrected_intent_id])
    document: Mapped[Optional["Document"]] = relationship("Document", back_populates="query_logs")


class Integration(Base):
    """Frontend integration configurations (Telegram, Teams)."""
    __tablename__ = "integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), unique=True)  # telegram, teams
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Encrypted token/webhook URL
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
