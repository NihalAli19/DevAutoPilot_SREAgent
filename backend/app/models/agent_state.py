"""Agent state / action Pydantic models."""
# TODO(plan: Phase 3) — model agent steps, tokens, latency, trace ids.
from __future__ import annotations

from pydantic import BaseModel


class AgentState(BaseModel):
    """Minimal agent-state stub."""

    org_id: str
    incident_id: str
    agent_name: str
    status: str = "started"
