"""Tests for EmbeddingService (no live network call)."""

import pytest

from app.config import Settings
from app.services.embedding_service import EmbeddingService


@pytest.mark.asyncio
async def test_embed_raises_when_gemini_key_missing():
    service = EmbeddingService(Settings(gemini_api_key=None))

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        await service.embed("hello")
