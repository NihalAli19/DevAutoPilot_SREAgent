"""Tests for RAGService: chunking, ingest, and retrieve (no live Azure/Gemini)."""

import pytest

from app.config import Settings
from app.models.knowledge import KnowledgeChunk
from app.services.rag_service import RAGService


class FakeEmbedder:
    """Deterministic vector per text (stands in for EmbeddingService)."""

    def __init__(self):
        self.calls: list[str] = []

    async def embed(self, text):
        self.calls.append(text)
        return [float(len(text))]


class FakeSearchClient:
    """In-memory vector store (stands in for AzureSearchClient)."""

    def __init__(self):
        self.uploaded: list[dict] = []

    async def upload(self, documents):
        self.uploaded.extend(documents)

    async def vector_search(self, vector, k):
        return [
            {"source": d["source"], "content": d["content"], "@search.score": 0.9}
            for d in self.uploaded[:k]
        ]


@pytest.mark.asyncio
async def test_ingest_chunks_embeds_and_uploads():
    embedder, client = FakeEmbedder(), FakeSearchClient()
    rag = RAGService(search_client=client, embedder=embedder)
    para_one, para_two = "a" * 500, "b" * 500  # each over half of max_chars -> two chunks

    count = await rag.ingest("latency-spike", f"{para_one}\n\n{para_two}")

    assert count == 2
    assert [d["id"] for d in client.uploaded] == ["latency-spike-0", "latency-spike-1"]
    assert client.uploaded[0]["source"] == "latency-spike"
    assert client.uploaded[0]["content"] == para_one
    assert client.uploaded[0]["embedding"] == [float(len(para_one))]
    assert embedder.calls == [para_one, para_two]


@pytest.mark.asyncio
async def test_ingest_merges_short_paragraphs_into_one_chunk():
    rag = RAGService(search_client=FakeSearchClient(), embedder=FakeEmbedder())

    count = await rag.ingest("short", "a\n\nb\n\nc")

    assert count == 1


@pytest.mark.asyncio
async def test_retrieve_returns_knowledge_chunks():
    client = FakeSearchClient()
    rag = RAGService(search_client=client, embedder=FakeEmbedder())
    await rag.ingest("runbook", "only paragraph")

    results = await rag.retrieve("what do I do", k=1)

    assert results == [KnowledgeChunk(source="runbook", content="only paragraph", score=0.9)]


@pytest.mark.asyncio
async def test_raises_when_azure_search_not_configured():
    rag = RAGService(
        embedder=FakeEmbedder(),
        settings=Settings(azure_search_endpoint=None, azure_search_key=None),
    )

    with pytest.raises(RuntimeError, match="Azure AI Search is not configured"):
        await rag.retrieve("query")
