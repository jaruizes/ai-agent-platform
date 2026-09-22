from __future__ import annotations

import hashlib
import math

from app.business.embeddings import EmbeddingResult


class HashEmbeddingProvider:
    """Deterministic credential-free embeddings for local/dev execution.

    This provider is intentionally lightweight and portable. It offers lexical-semantic
    locality through feature hashing, but is not a substitute for a production-grade
    embedding model. The Knowledge layer depends on the provider abstraction, so a
    remote/cloud provider can replace it without changing ingestion or retrieval flows.
    """

    def __init__(
        self,
        *,
        dimensions: int = 768,
        model: str = "hash-embedding-v1",
    ):
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")
        self._dimensions = dimensions
        self._model = model

    @property
    def provider_key(self) -> str:
        return "hash"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[self._embed_text(text) for text in texts],
            model=self._model,
            dimensions=self._dimensions,
        )

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = text.lower().split()
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector
