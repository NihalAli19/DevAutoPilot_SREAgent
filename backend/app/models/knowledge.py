"""Types for retrieved RAG context (runbooks, past postmortems)."""

from __future__ import annotations

from pydantic import BaseModel


class KnowledgeChunk(BaseModel):
    """A single retrieved passage plus its source and similarity score."""

    source: str
    content: str
    score: float | None = None
