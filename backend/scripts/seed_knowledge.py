"""Embed and upload the seed runbooks into Azure AI Search via RAGService.

Run once the Azure AI Search index exists (see create_search_index.py) and
AZURE_SEARCH_ENDPOINT/AZURE_SEARCH_KEY/GEMINI_API_KEY are set.

Run from backend/:  python -m scripts.seed_knowledge
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.rag_service import RAGService

_RUNBOOKS_DIR = Path(__file__).resolve().parents[2] / "ml" / "data" / "runbooks"


async def seed() -> None:
    rag = RAGService()
    paths = sorted(_RUNBOOKS_DIR.glob("*.md"))
    total = 0
    for path in paths:
        count = await rag.ingest(path.stem, path.read_text(encoding="utf-8"))
        print(f"ingested {path.name}: {count} chunk(s)")
        total += count
    print(f"done: {total} chunk(s) across {len(paths)} runbook(s)")


if __name__ == "__main__":
    asyncio.run(seed())
