"""RAGService — chunk, embed, and retrieve incident-knowledge passages.

Vector storage/search lives in **Azure AI Search** (per docs/IMPLEMENTATION_PLAN.md —
a deliberately listed competency, not an implementation detail); Postgres stays
relational/audit-only. Embeddings come from Gemini (EmbeddingService), decoupled from
the vector store so either side can change independently.

Azure AI Search access is behind the ``SearchClient`` protocol so this module — and its
tests — never require live Azure credentials; ``AzureSearchClient`` is the real adapter,
wired up once ``AZURE_SEARCH_ENDPOINT``/``AZURE_SEARCH_KEY`` are set.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from app.config import Settings, get_settings
from app.models.knowledge import KnowledgeChunk
from app.services.embedding_service import EmbeddingService

INDEX_NAME = "knowledge-chunks"
EMBEDDING_FIELD = "embedding"


class Embedder(Protocol):
    """Anything that can turn text into a vector (EmbeddingService, or a fake)."""

    async def embed(self, text: str) -> list[float]: ...


class SearchClient(Protocol):
    """Minimal vector-store interface RAGService needs (Azure AI Search, or a fake)."""

    async def upload(self, documents: list[dict[str, Any]]) -> None: ...

    async def vector_search(self, vector: list[float], k: int) -> list[dict[str, Any]]: ...


class AzureSearchClient:
    """Real adapter over ``azure-search-documents`` (async), targeting ``INDEX_NAME``."""

    def __init__(self, endpoint: str, key: str, index_name: str = INDEX_NAME) -> None:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents.aio import SearchClient as _AsyncSearchClient

        self._client = _AsyncSearchClient(
            endpoint=endpoint, index_name=index_name, credential=AzureKeyCredential(key)
        )

    async def upload(self, documents: list[dict[str, Any]]) -> None:
        await self._client.upload_documents(documents=documents)

    async def vector_search(self, vector: list[float], k: int) -> list[dict[str, Any]]:
        from azure.search.documents.models import VectorizedQuery

        query = VectorizedQuery(vector=vector, k_nearest_neighbors=k, fields=EMBEDDING_FIELD)
        results = await self._client.search(vector_queries=[query], top=k)
        return [dict(hit) async for hit in results]


class RAGService:
    """Ingest runbook/postmortem text and retrieve the most relevant passages."""

    def __init__(
        self,
        *,
        search_client: SearchClient | None = None,
        embedder: Embedder | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._search_client = search_client
        self.embedder = embedder or EmbeddingService(self.settings)

    def _client(self) -> SearchClient:
        if self._search_client is not None:
            return self._search_client
        s = self.settings
        if not (s.azure_search_endpoint and s.azure_search_key):
            raise RuntimeError(
                "Azure AI Search is not configured; set AZURE_SEARCH_ENDPOINT and "
                "AZURE_SEARCH_KEY in .env"
            )
        return AzureSearchClient(s.azure_search_endpoint, s.azure_search_key)

    async def ingest(self, source: str, content: str) -> int:
        """Chunk, embed, and upload ``content``; return the number of chunks stored."""
        chunks = _chunk(content)
        slug = _slugify(source)
        documents = [
            {
                "id": f"{slug}-{i}",
                "source": source,
                "content": chunk,
                EMBEDDING_FIELD: await self.embedder.embed(chunk),
            }
            for i, chunk in enumerate(chunks)
        ]
        await self._client().upload(documents)
        return len(documents)

    async def retrieve(self, query: str, k: int = 3) -> list[KnowledgeChunk]:
        """Return the top-``k`` passages most relevant to ``query``."""
        vector = await self.embedder.embed(query)
        hits = await self._client().vector_search(vector, k)
        return [
            KnowledgeChunk(
                source=hit["source"], content=hit["content"], score=hit.get("@search.score")
            )
            for hit in hits
        ]


def _chunk(content: str, max_chars: int = 800) -> list[str]:
    """Split on blank lines (paragraphs), merging short ones up to ``max_chars``."""
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        candidate = f"{current}\n\n{p}" if current else p
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = p
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _slugify(source: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", source.lower()).strip("-")
