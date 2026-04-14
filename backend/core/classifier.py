"""
Intent classifier using LLM for query classification.
"""

import json
import logging
import re
from typing import Sequence, Dict, Any
from sqlalchemy import select

from core.database import SessionLocal
from core.config import settings
from models import IntentSpace
from services.llm_factory import LLMFactory

logger = logging.getLogger("kms.classifier")


class IntentClassifier:
    """Classifies user queries into intent spaces using LLM."""

    def __init__(self):
        self.confidence_threshold = settings.intent_confidence_threshold

    async def classify(self, query: str) -> Dict[str, Any]:
        """
        Classify a query into an intent space.
        Returns dict with intent_id, intent_name, and confidence.
        """
        # Get all intent spaces
        with SessionLocal() as db:
            result = db.execute(select(IntentSpace))
            intent_spaces = result.scalars().all()

        if not intent_spaces:
            return {
                "intent_id": None,
                "intent_name": "General",
                "confidence": 0.0
            }

        # Build classification prompt
        intent_list = "\n".join([
            f"- {space.name}: {space.description or 'No description'} (keywords: {space.keywords or 'none'})"
            for space in intent_spaces
        ])

        prompt = f"""You are an intent classifier for a knowledge management system.
Given the user query, classify it into one of the following intent categories:

{intent_list}

User Query: {query}

Respond with ONLY a JSON object in this format:
{{"intent": "category_name", "confidence": 0.0-1.0}}

If the query doesn't clearly match any category, use "General" as the intent.
Confidence should reflect how certain you are (higher = more confident).
"""

        try:
            llm = LLMFactory.get_llm()
            response = await llm.generate([{"role": "user", "content": prompt}])

            # Parse JSON response
            response_text = response.strip()
            # Handle markdown code blocks
            if response_text.startswith("```"):
                response_text = re.sub(r'^```json?\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)

            result = json.loads(response_text)

            intent_name = result.get("intent", "Unknown")
            confidence = float(result.get("confidence", 0.0))

            # Find matching intent
            matched_space = None
            for space in intent_spaces:
                if space.name.lower() == intent_name.lower():
                    matched_space = space
                    break

            # If no match, default to "General" intent
            if not matched_space:
                logger.warning("LLM classification returned unknown intent, falling back to default")
                result = self._fallback_result(intent_spaces)
                return result

            logger.info(f"Classification result: intent_id={matched_space.id}, intent_name={matched_space.name}, confidence={confidence}")
            return {
                "intent_id": matched_space.id,
                "intent_name": matched_space.name,
                "confidence": confidence
            }

        except Exception as e:
            logger.warning(f"LLM classification failed, falling back to keyword classification: {e}")
            # Fallback: keyword-based classification
            return self._fallback_classify(query, intent_spaces)

    def _fallback_classify(
        self,
        query: str,
        intent_spaces: Sequence[IntentSpace]
    ) -> Dict[str, Any]:
        """
        Fallback keyword-based classification when LLM fails.
        """
        query_lower = query.lower()
        best_match = None
        best_score = 0

        for space in intent_spaces:
            if not space.keywords:
                continue

            keywords = [k.strip().lower() for k in space.keywords.split(",")]
            score = sum(1 for kw in keywords if kw in query_lower)

            if score > best_score:
                best_score = score
                best_match = space

        if best_match and best_score > 0:
            return {
                "intent_id": best_match.id,
                "intent_name": best_match.name,
                "confidence": min(0.5 + best_score * 0.1, 0.9)  # Cap at 0.9
            }

        # Default to "General" intent
        return self._fallback_result(intent_spaces)

    def _fallback_result(
        self,
        intent_spaces: Sequence[IntentSpace]
    ) -> Dict[str, Any]:
        """
        Lookup "General" intent info in the intent spaces as the fallback result.
        """
        general_intent = next(
            (s for s in intent_spaces if s.name.lower() == "general"),
            None
        )

        return {
            "intent_id": general_intent.id if general_intent else None,
            "intent_name": "General",
            "confidence": 0.0
        }
