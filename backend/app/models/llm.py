"""Minimal LLM message/result types shared by the router and agents."""

# TODO(plan: Phase 2/3) — add token/cost fields once budgets are enforced.
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    """A single chat message."""

    role: Role
    content: str


class LLMResult(BaseModel):
    """The model's reply plus which provider/model produced it."""

    content: str
    model: str
    provider: str
