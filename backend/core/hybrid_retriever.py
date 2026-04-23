"""
Hybrid retriever combining FTS5 and vector search with weighted scoring.
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

from core.database import SessionLocal
from core.document_store import get_doc_store
from core.config import settings

logger = logging.getLogger("kms.retriever")


class HybridRetriever:
    """
    Combines FTS5 (full-text) and vector search with configurable weights.
    Default weights: text=0.3, vector=0.7
    """

    def __init__(
        self,
        text_weight: Optional[float] = None,
        vector_weight: Optional[float] = None,
        top_k: int = 50,
        doc_store: Optional[Any] = None
    ):
        self.text_weight = text_weight or settings.hybrid_weight_text
        self.vector_weight = vector_weight or settings.hybrid_weight_vector
        self.top_k = top_k
        self.doc_store = doc_store or get_doc_store()

    def retrieve(
        self,
        query_text: str,
        query_embedding: np.ndarray,
        intent_id: Optional[int] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant document chunks using hybrid search.
        Combines FTS5 and vector results with weighted scoring.

        Args:
            query_text: The user's query string
            query_embedding: Pre-computed embedding for the query
            intent_id: Optional filter by intent space
            top_k: Number of results to return

        Returns:
            List of dicts with content, scores, and document info
        """
        logger.info(f"Retrieving documents for query: '{query_text[:50]}...', intent_id={intent_id}")

        try:
            # 1. Get FTS5 results
            fts_results = self.doc_store.search_fts(query_text, self.top_k)
            logger.info(f"FTS search returned {len(fts_results)} results")

            # 2. Get vector results
            vec_results = self.doc_store.search_vector(query_embedding, self.top_k)
            logger.info(f"Vector search returned {len(vec_results)} results")

            # 3. Build combined result set
            combined_scores: Dict[str, Dict[str, Any]] = {}

            # Process FTS results
            if fts_results:
                max_fts_score = max(r["text_score"] for r in fts_results)
                min_fts_score = min(r["text_score"] for r in fts_results)
                fts_range = max_fts_score - min_fts_score if max_fts_score != min_fts_score else 1

                for result in fts_results:
                    chunk_id = result["chunk_id"]
                    normalized_score = (result["text_score"] - min_fts_score) / fts_range
                    combined_scores[chunk_id] = {
                        "chunk_id": chunk_id,
                        "content": result["content"],
                        "text_score": normalized_score,
                        "vector_score": 0.0,
                        "document_id": self._extract_doc_id(chunk_id)
                    }

            # Process vector results
            if vec_results:
                max_vec_score = max(r["vector_score"] for r in vec_results)
                min_vec_score = min(r["vector_score"] for r in vec_results)
                vec_range = max_vec_score - min_vec_score if max_vec_score != min_vec_score else 1

                for result in vec_results:
                    # vec_chunks rowid equals chunks.id
                    chunk_id = self._get_chunk_id_from_rowid(result["rowid"])
                    if not chunk_id:
                        continue

                    if chunk_id in combined_scores:
                        combined_scores[chunk_id]["vector_score"] = (
                            result["vector_score"] - min_vec_score
                        ) / vec_range
                    else:
                        combined_scores[chunk_id] = {
                            "chunk_id": chunk_id,
                            "content": "",  # Will be fetched
                            "text_score": 0.0,
                            "vector_score": (result["vector_score"] - min_vec_score) / vec_range,
                            "document_id": self._extract_doc_id(chunk_id)
                        }

            logger.info(f"Combined result set built: {len(combined_scores)} items")

            # 4. Calculate final scores
            results = []
            for chunk_id, data in combined_scores.items():
                final_score = (
                    self.text_weight * data["text_score"] +
                    self.vector_weight * data["vector_score"]
                )

                # Fetch full content if missing
                if not data["content"]:
                    chunk_data = self.doc_store.get_chunk_by_id(chunk_id)
                    data["content"] = chunk_data["content"] if chunk_data else ""

                results.append({
                    "chunk_id": chunk_id,
                    "content": data["content"],
                    "final_score": final_score,
                    "text_score": data["text_score"],
                    "vector_score": data["vector_score"],
                    "document_id": data["document_id"]
                })

            # 5. Sort by final score and filter by intent if specified
            results.sort(key=lambda x: x["final_score"], reverse=True)

            # Filter by intent if specified
            if intent_id:
                results = self._filter_by_intent(results, intent_id)

            # 6. Return top_k
            final_results = results[:top_k]
            logger.info(f"Retrieval completed: {len(final_results)} results")
            return final_results

        except Exception as e:
            logger.error(f"Retrieval failed for query '{query_text[:50]}...': {e}")
            raise

    def _filter_by_intent(self, results: List[Dict], intent_id: int) -> List[Dict]:
        """Filter results by intent space."""
        with SessionLocal() as db:
            from sqlalchemy import text
            doc_ids_result = db.execute(
                text("SELECT id FROM documents WHERE intent_space_id = :intent_id"),
                {"intent_id": intent_id}
            )
            valid_doc_ids = {row[0] for row in doc_ids_result.all()}

        filtered = [r for r in results if r["document_id"] in valid_doc_ids]

        # If no intent-specific results, return all (fallback)
        return filtered if filtered else results

    def _extract_doc_id(self, chunk_id: str) -> Optional[int]:
        """Extract document ID from chunk_id (format: docId_chunkIndex)."""
        try:
            return int(chunk_id.split("_")[0])
        except (ValueError, IndexError):
            return None

    def _get_chunk_id_from_rowid(self, rowid: int) -> Optional[str]:
        """Get chunk_id from fts_chunks using rowid."""
        with SessionLocal() as db:
            from sqlalchemy import text
            result = db.execute(
                text("SELECT chunk_id FROM fts_chunks WHERE rowid = :rowid"),
                {"rowid": rowid}
            )
            row = result.first()
            return row[0] if row else None
