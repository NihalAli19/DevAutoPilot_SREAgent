"""EmbeddingService — turns text into vectors via Gemini's embedding endpoint.

Reuses ``GEMINI_API_KEY`` (no new secret); the vectors are provider-agnostic and get
stored in whichever vector store RAGService is configured with (Azure AI Search).
"""

from __future__ import annotations

import httpx

from app.config import Settings, get_settings

GEMINI_EMBED_MODEL = "models/text-embedding-004"
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class EmbeddingService:
    """Embeds text into fixed-size vectors for RAG indexing/retrieval."""

    def __init__(
        self, settings: Settings | None = None, *, model: str = GEMINI_EMBED_MODEL
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model

    async def embed(self, text: str) -> list[float]:
        """Return the embedding vector for ``text``."""
        key = self.settings.gemini_api_key
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set; required to compute embeddings")
        url = f"{_GEMINI_BASE_URL}/{self.model}:embedContent"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url, params={"key": key}, json={"content": {"parts": [{"text": text}]}}
            )
            resp.raise_for_status()
        return resp.json()["embedding"]["values"]
