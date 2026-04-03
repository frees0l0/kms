#pylint: disable=global-statement,invalid-name
"""
Orchestrator for handling bot messages with RAG pipeline.
Coordinates intent classification, document retrieval, and response generation.
"""

import logging
import time
from typing import Any, Dict

from utils.timing import StopWatch

from core.classifier import IntentClassifier
from core.hybrid_retriever import HybridRetriever
from core.document_store import DocumentStore
from models import QueryLog
from services.llm_factory import LLMFactory

logger = logging.getLogger("kms.orchestrator")


# Lazy initialization of AI components
_classifier = None
_retriever = None
_doc_store = None


def get_classifier() -> IntentClassifier:
    """Get global classifier"""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


def get_retriever() -> HybridRetriever:
    """Get global retriever"""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


def get_doc_store() -> DocumentStore:
    """Get global doc store"""
    global _doc_store
    if _doc_store is None:
        _doc_store = DocumentStore()
    return _doc_store


async def process_query(
    query_text: str,
    source: str,
    chat_id: str
) -> Dict[str, Any]:
    """
    Process a query: classify intent, retrieve documents, generate response.

    Args:
        query_text: The user's query string
        source: Message source ('telegram' or 'teams')
        chat_id: User/bot chat identifier

    Returns:
        Dict with response, intent_id, intent_name, confidence, document_id, response_time_ms
    """
    from core.database import SessionLocal

    logger.info(f"Processing query from {source}, chat_id={chat_id}")

    start_time = time.time()

    with SessionLocal() as db:
        # Validate source
        if source not in ("telegram", "teams"):
            raise ValueError("Invalid source. Must be 'telegram' or 'teams'")

        try:
            # 1. Classify intent
            with StopWatch() as sw:
                classifier = get_classifier()
                intent_result = await classifier.classify(query_text)
            logger.info(f"Step 1 - Intent classification: {sw.elapsed_ms}ms, intent={intent_result.get('intent_name')}, confidence={intent_result.get('confidence')}")

            intent_id = intent_result.get("intent_id")
            confidence = intent_result.get("confidence")
            intent_name = intent_result.get("intent_name", "General")

            # 2. Generate query embedding
            with StopWatch() as sw:
                doc_store = get_doc_store()
                query_embedding = await doc_store.get_query_embedding(query_text)
            logger.info(f"Step 2 - Query embedding: {sw.elapsed_ms}ms")

            # 3. Retrieve relevant documents (hybrid search)
            with StopWatch() as sw:
                retriever = get_retriever()
                retrieved_chunks = retriever.retrieve(
                    query_text=query_text,
                    query_embedding=query_embedding,
                    intent_id=intent_id,
                    top_k=3
                )
            logger.info(f"Step 3 - Document retrieval: {sw.elapsed_ms}ms, chunks_found={len(retrieved_chunks)}")

            # 4. Generate response using LLM with RAG context
            with StopWatch() as sw:
                response_text = await _generate_rag_response(
                    query=query_text,
                    chunks=retrieved_chunks,
                    intent_name=intent_name
                )
            logger.info(f"Step 4 - RAG response generation: {sw.elapsed_ms}ms")

            # 4. Get most relevant document ID
            document_id = retrieved_chunks[0].get("document_id") if retrieved_chunks else None

            # 5. Log the query
            response_time_ms = int((time.time() - start_time) * 1000)

            query_log = QueryLog(
                source=source,
                user_id=chat_id,
                query_text=query_text,
                intent_id=intent_id,
                confidence=confidence,
                response_text=response_text,
                response_time_ms=response_time_ms,
                document_id=document_id
            )
            db.add(query_log)
            db.commit()

            logger.info(f"Query completed: intent_id={intent_id}, confidence={confidence}, response_time_ms={response_time_ms}")

            return {
                "response": response_text,
                "intent_id": intent_id,
                "intent_name": intent_name,
                "confidence": confidence,
                "document_id": document_id,
                "response_time_ms": response_time_ms
            }

        except Exception as e:
            logger.error(f"Query processing failed for chat_id={chat_id}: {e}")

            response_time_ms = int((time.time() - start_time) * 1000)

            error_log = QueryLog(
                source=source,
                user_id=chat_id,
                query_text=query_text,
                response_text="I apologize, but I encountered an error processing your request.",
                response_time_ms=response_time_ms
            )
            db.add(error_log)
            db.commit()

            raise


async def _generate_rag_response(query: str, chunks: list, intent_name: str) -> str:
    """
    Generate response using RAG (Retrieval Augmented Generation).
    Combines retrieved context with LLM to generate an answer.
    """
    # Build context from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(chunks[:3], 1):
        content = chunk.get("content", "")
        doc_name = chunk.get("document_name", "Unknown document")
        context_parts.append(f"[Document {i}] ({doc_name}):\n{content}")

    context = "\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # Create prompt
    prompt = f"""You are an AI assistant for an enterprise knowledge management system.

Intent Category: {intent_name}

User Query: {query}

Relevant Context:
{context}

Based on the context above, please answer the user's query. If the context doesn't contain relevant information, say so and provide a helpful response based on your general knowledge.

Answer:"""

    # Generate response
    llm = LLMFactory.get_llm()
    response = await llm.generate([{"role": "user", "content": prompt}])

    return response
