"""
LLM Factory - Unified LLM client supporting OpenAI and compatible APIs.
"""

import logging
from typing import Any, List

import httpx
import numpy as np
import openai

from core.config import settings

logger = logging.getLogger("kms.llm")


class LLMFactory:
    """Factory for creating LLM clients."""

    _llm_client = None
    _embedding_client = None

    @classmethod
    def get_llm(cls):
        """Get the main LLM client for chat completions."""
        if cls._llm_client is None:
            cls._llm_client = OpenAIClient(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.default_llm_model
            )
            logger.info(f"LLM client initialized: model={settings.default_llm_model}, base_url={settings.openai_base_url}")
        return cls._llm_client

    @classmethod
    def get_embedding_model(cls):
        """Get the embedding model client."""
        if cls._embedding_client is None:
            cls._embedding_client = EmbeddingClient(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.default_embedding_model,
                dimensions=settings.default_embedding_dim
            )
            logger.info(f"Embedding client initialized: model={settings.default_embedding_model}, dimensions={settings.default_embedding_dim}")
        return cls._embedding_client


class OpenAIClient:
    """OpenAI-compatible chat completion client."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            http_client=httpx.AsyncClient()
        )

    async def generate(self, messages: Any) -> str:
        """
        Generate a chat completion asynchronously.
        messages: List of {"role": "user"/"assistant"/"system", "content": str}
        """
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM generation failed: model={self.model}, error={e}")
            if not self.api_key:
                return self._generate_mock_response(messages)
            raise e

    def _generate_mock_response(self, messages: Any) -> str:
        """Generate a mock response when no API key is configured."""
        last_message = messages[-1]["content"] if messages else ""
        return f"Mock response to: {last_message[:100]}... (Configure OPENAI_API_KEY for real responses)"


class EmbeddingClient:
    """OpenAI-compatible embedding client."""

    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int = 1024):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            http_client=httpx.AsyncClient()
        )

    async def embed(self, text: str) -> List[float]:
        """
        Generate embeddings asynchronously.
        Returns a list of floats (embedding dimensions).
        """
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: model={self.model}, error={e}")
            raise
