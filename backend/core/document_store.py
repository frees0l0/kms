"""
Document storage with SQLite FTS5 and sqlitevec for hybrid search.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np
import spacy
from sqlalchemy import text

from core.config import settings
from core.database import SessionLocal
from models import Chunk
from services.llm_factory import LLMFactory

logger = logging.getLogger("kms.docstore")


class FTS5Preprocessor:
    """
    FTS5 text preprocessor using spaCy for tokenization.
    Supports both Chinese and English text with stopword filtering.
    """

    def __init__(self):
        # Load spaCy models with NER and parser disabled for speed
        self.nlp_zh = spacy.load("zh_core_web_sm", disable=["ner", "parser"])
        self.nlp_en = spacy.load("en_core_web_sm", disable=["ner", "parser"])

    def preprocess(self, text: str) -> str:
        """
        Route text to the appropriate language processor.
        Returns a space-separated string of processed tokens.
        """
        if self._is_chinese_dominant(text):
            return self._process_chinese(text)
        else:
            return self._process_english(text)

    def _is_chinese_dominant(self, text: str) -> bool:
        """Check if Chinese characters make up more than 30% of the text."""
        if not text:
            return False
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        return chinese_chars / len(text) > 0.3

    def _process_chinese(self, text: str) -> str:
        """Tokenize Chinese text with spaCy, remove punctuation and stopwords."""
        doc = self.nlp_zh(text)
        tokens = [
            token.text for token in doc
            if not token.is_stop and not token.is_punct and len(token.text) > 1
        ]
        return " ".join(tokens)

    def _process_english(self, text: str) -> str:
        """Tokenize English text with spaCy, lemmatize, lowercase, remove punctuation and stopwords."""
        doc = self.nlp_en(text)
        tokens = [
            token.lemma_.lower() for token in doc
            if not token.is_stop and not token.is_punct
        ]
        return " ".join(tokens)


class DocumentStore:
    """Manages document storage with FTS5 and vector embeddings."""

    _instance = None

    def __init__(self):
        self.embedding_dim = settings.default_embedding_dim
        self.preprocessor = FTS5Preprocessor()

    @classmethod
    def get_instance(cls) -> "DocumentStore":
        """Get global DocumentStore singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self):
        """Initialize FTS5 and vec tables if they don't exist."""
        logger.info("Initializing document store: creating FTS5 and vec tables if needed")
        with SessionLocal() as db:
            # Create FTS5 table for full-text search
            db.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
                    content,
                    chunk_id UNINDEXED
                )
            """))

            # Try to create sqlitevec table for vector search
            # Note: vec0 extension must be loaded first - may fail if SQLite has extensions disabled
            try:
                db.execute(text(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                        embedding float[{self.embedding_dim}]
                    )
                """))
            except Exception as e:
                logger.warning(f"vec0 not available, skipping vector table creation: {e}")

            db.commit()

    async def store_document(self, document_id: int, chunks_data: List[Dict[str, Any]]):
        """
        Store document chunks in chunks table, FTS5, and vector tables.
        chunks_data: List of {"content": str, "metadata": dict}
        """
        logger.info(f"Storing document: document_id={document_id}, chunks={len(chunks_data)}")
        # Generate embeddings before transaction to minimize lock time
        if settings.sqlite_vec_loaded:
            for chunk in chunks_data:
                try:
                    chunk["embedding"] = await self._generate_embedding(chunk["content"])
                except Exception as e:
                    logger.warning(f"embedding generation failed: {e}")

        # Run database work in thread pool to avoid blocking event loop
        await asyncio.to_thread(self._store_chunks, document_id, chunks_data)

    def _store_chunks(self, document_id: int, chunks_data: List[Dict[str, Any]]):
        """Store chunks for a document after deleting old ones."""
        with SessionLocal() as db:
            # Delete old chunks first
            self._delete_chunks(db, document_id)

            # Insert new chunks
            for chunk in chunks_data:
                content = chunk["content"]
                metadata = chunk.get("metadata", {})
                chunk_index = metadata.get("chunk_index", 0)

                # Save to chunks table
                db_chunk = Chunk(
                    document_id=document_id,
                    content=content,
                    chunk_metadata=metadata
                )
                db.add(db_chunk)
                db.flush()  # Get the chunk id

                # Insert into fts_chunks (FTS5) with explicit rowid
                db.execute(
                    text("INSERT INTO fts_chunks(rowid, content, chunk_id) VALUES (:rowid, :content, :chunk_id)"),
                    {"rowid": db_chunk.id, "content": self.preprocessor.preprocess(content), "chunk_id": f"{document_id}_{chunk_index}"}
                )

                # Store vector embedding if already generated
                embedding = chunk.get("embedding")
                if embedding is not None:
                    try:
                        db.execute(
                            text("INSERT INTO vec_chunks(rowid, embedding) VALUES (:rowid, :embedding)"),
                            {"rowid": db_chunk.id, "embedding": json.dumps(embedding.tolist())}
                        )
                    except Exception as e:
                        logger.warning(f"vector storage failed: {e}")

            db.commit()

    def delete_document(self, document_id: int):
        """Delete all chunks for a document from chunks table, FTS5, and vector tables."""
        logger.info(f"Deleting document: document_id={document_id}")
        with SessionLocal() as db:
            self._delete_chunks(db, document_id)
            db.commit()

    def _delete_chunks(self, db, document_id: int):
        """Delete all chunks for a document from all tables. Reusable internal method."""
        result = db.execute(
            text("SELECT id FROM chunks WHERE document_id = :document_id"),
            {"document_id": document_id}
        )
        chunk_ids = [row[0] for row in result.all()]

        if chunk_ids:
            db.execute(
                text("DELETE FROM chunks WHERE document_id = :document_id"),
                {"document_id": document_id}
            )

        pattern = f"{document_id}_%"
        db.execute(
            text("DELETE FROM fts_chunks WHERE chunk_id LIKE :pattern"),
            {"pattern": pattern}
        )

        if settings.sqlite_vec_loaded:
            for chunk_id in chunk_ids:
                try:
                    db.execute(
                        text("DELETE FROM vec_chunks WHERE rowid = :rowid"),
                        {"rowid": chunk_id}
                    )
                except Exception as e:
                    logger.warning(f"vector deletion failed: {e}")

    def search_fts(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Full-text search using FTS5.
        Returns chunks with BM25 scores converted to similarity.
        """
        # Normalize query with spaCy preprocessor before FTS MATCH
        normalized = self.preprocessor.preprocess(query)
        # Use normalized tokens as OR-separated query terms
        tokens = normalized.split() if normalized else []
        sanitized = ' OR '.join(tokens)

        with SessionLocal() as db:
            result = db.execute(
                text("""
                    SELECT chunk_id, content,
                           bm25(fts_chunks) as bm25_score
                    FROM fts_chunks
                    WHERE fts_chunks MATCH :query
                    ORDER BY bm25_score
                    LIMIT :limit
                """),
                {"query": sanitized, "limit": top_k}
            )

            rows = result.all()
            if not rows:
                logger.info(f"FTS search: query='{sanitized}', top_k={top_k}, results=0")
                return []

            # Get min/max BM25 for normalization
            scores = [row[2] for row in rows]
            min_score, max_score = min(scores), max(scores)
            range_score = max_score - min_score if max_score != min_score else 1

            results = []
            for chunk_id, content, bm25_score in rows:
                # Convert BM25 (lower is better) to similarity (higher is better)
                similarity = 1.0 - (bm25_score - min_score) / range_score
                results.append({
                    "chunk_id": chunk_id,
                    "content": content,
                    "text_score": max(0, similarity)
                })

            logger.info(f"FTS search: query='{sanitized}', top_k={top_k}, results={len(results)}")
            return results

    def search_vector(self, embedding: np.ndarray, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Vector search using sqlitevec.
        Returns chunks with cosine distance converted to similarity.
        Returns empty list if vec0 extension is not available.
        """
        if not settings.sqlite_vec_loaded:
            return []

        with SessionLocal() as db:
            embedding_json = json.dumps(embedding.tolist())

            result = db.execute(
                text("""
                    SELECT rowid, distance
                    FROM vec_chunks
                    WHERE embedding MATCH :embedding
                    ORDER BY distance
                    LIMIT :limit
                """),
                {"embedding": embedding_json, "limit": top_k}
            )

            rows = result.all()
            if not rows:
                logger.info(f"Vector search: top_k={top_k}, results=0")
                return []

            # Get min/max distance for normalization
            distances = [row[1] for row in rows]
            min_dist, max_dist = min(distances), max(distances)
            range_dist = max_dist - min_dist if max_dist != min_dist else 1

            results = []
            for rowid, distance in rows:
                # Convert distance to similarity
                similarity = 1.0 - (distance - min_dist) / range_dist
                results.append({
                    "rowid": rowid,
                    "vector_distance": distance,
                    "vector_score": max(0, similarity)
                })

            logger.info(f"Vector search: top_k={top_k}, results={len(results)}")
            return results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific chunk by its ID."""
        with SessionLocal() as db:
            result = db.execute(
                text("SELECT content, chunk_id FROM fts_chunks WHERE chunk_id = :chunk_id"),
                {"chunk_id": chunk_id}
            )
            row = result.first()
            if row:
                return {"content": row[0], "chunk_id": row[1]}
            return None

    async def get_query_embedding(self, query_text: str) -> np.ndarray:
        """Generate embedding for a query string."""
        return await self._generate_embedding(query_text)

    async def _generate_embedding(self, input_text: str) -> np.ndarray:
        """
        Generate embedding using the configured LLM.
        Falls back to a simple hash-based embedding if no LLM configured.
        """
        llm = LLMFactory.get_embedding_model()
        embedding = await llm.embed(input_text)
        return np.array(embedding)


def get_doc_store() -> DocumentStore:
    """Get global doc store singleton."""
    return DocumentStore.get_instance()
