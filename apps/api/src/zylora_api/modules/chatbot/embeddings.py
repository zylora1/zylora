from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx
import numpy as np
from zylora_api.core.config import Settings


class EmbeddingProviderError(Exception):
    """A safe provider failure; callers must not activate an incomplete index."""


class EmbeddingProvider(Protocol):
    model: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model = settings.chatbot_embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or not self._settings.openai_api_key:
            raise EmbeddingProviderError
        try:
            async with httpx.AsyncClient(timeout=self._settings.ai_timeout_seconds) as client:
                response = await client.post(
                    f"{self._settings.openai_base_url.rstrip('/')}/embeddings",
                    headers={"Authorization": f"Bearer {self._settings.openai_api_key}"},
                    json={"model": self.model, "input": texts},
                )
                response.raise_for_status()
                body = response.json()
            rows = body.get("data")
            if not isinstance(rows, list) or len(rows) != len(texts):
                raise ValueError("embedding response has unexpected shape")
            vectors: list[list[float]] = []
            for item in rows:
                raw_vector = item.get("embedding") if isinstance(item, dict) else None
                if not isinstance(raw_vector, list):
                    raise ValueError("embedding response has invalid vectors")
                vectors.append([float(value) for value in raw_vector])
            if len(vectors) != len(texts):
                raise ValueError("embedding response has invalid vectors")
            return vectors
        except (httpx.HTTPError, OSError, TypeError, ValueError) as error:
            raise EmbeddingProviderError from error


class DeterministicEmbeddingProvider:
    """A deterministic test provider for FAISS isolation tests without network calls."""

    model = "deterministic-test-v1"

    def __init__(self, dimension: int = 64) -> None:
        if not 8 <= dimension <= 4096:
            raise ValueError("dimension must be between 8 and 4096")
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for value in texts:
            vector = np.zeros(self.dimension, dtype=np.float32)
            for position, token in enumerate(value.casefold().split()):
                digest = hashlib.blake2b(token.encode(), digest_size=16).digest()
                slot = int.from_bytes(digest[:4], "big") % self.dimension
                vector[slot] += 1.0 + (position % 3) * 0.1
            norm = math.sqrt(float(np.dot(vector, vector)))
            if norm == 0:
                vector[0] = 1.0
            else:
                vector /= norm
            vectors.append(vector.tolist())
        return vectors
