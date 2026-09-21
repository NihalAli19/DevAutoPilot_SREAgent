"""RCA Agent — RAG-grounded root-cause reasoning with persistence and audit."""

# TODO(plan: Phase 3c) — enrich RCA evidence with recent target-repository commits.

from __future__ import annotations

import json
from typing import Any, Protocol

from agent_framework import Agent
from pydantic import BaseModel, Field, ValidationError

from app.models.incident import Incident
from app.models.knowledge import KnowledgeChunk
from app.models.root_cause_analysis import RCAEvidence, RootCauseAnalysis
from app.services import db_service
from app.services.llm_router import LLMRouter
from app.services.rag_service import RAGService
from app.utils.prompts import (
    RCA_INSTRUCTIONS,
    build_rca_prompt,
    build_rca_query,
)
from app.utils.telemetry import agent_step_span, record_llm_usage


class Retriever(Protocol):
    """The retrieval surface consumed by the RCA Agent."""

    async def retrieve(self, query: str, k: int = 3) -> list[KnowledgeChunk]: ...


class RCAStore(Protocol):
    """Persistence surface consumed by the RCA Agent."""

    async def insert_root_cause_analysis(
        self, analysis: RootCauseAnalysis
    ) -> RootCauseAnalysis: ...

    async def insert_agent_action(
        self,
        *,
        org_id: str,
        agent_name: str,
        action: str,
        incident_id: str | None = None,
        status: str = "succeeded",
        output: dict[str, Any] | None = None,
    ) -> None: ...


class _ReasoningOutput(BaseModel):
    hypothesis: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    affected_files: list[str] = Field(default_factory=list)


class RCAAgent:
    """Retrieves incident evidence and persists an LLM-generated RCA hypothesis."""

    def __init__(
        self,
        *,
        rag_service: Retriever | None = None,
        chat_client: Any | None = None,
        llm_router: LLMRouter | None = None,
        store: RCAStore | None = None,
        top_k: int = 3,
    ) -> None:
        self.rag = rag_service or RAGService()
        self._chat_client = chat_client
        self.router = llm_router or LLMRouter()
        self.store = store or db_service
        self.top_k = top_k

    def _agent(self) -> Agent:
        client = self._chat_client or self.router.chat_client()
        return Agent(client, instructions=RCA_INSTRUCTIONS, name="rca")

    def _model_name(self) -> str:
        settings = self.router.settings
        if settings.llm_default_provider == "ollama":
            return settings.ollama_model
        if settings.llm_default_provider == "azure":
            return settings.azure_openai_deployment or settings.llm_cloud_model
        return settings.llm_cloud_model

    async def analyze(self, incident_id: str, incident: Incident) -> RootCauseAnalysis:
        """Retrieve evidence, reason over it, persist the RCA, and append an audit row."""
        try:
            with agent_step_span("rca", "rag.retrieve") as span:
                evidence = await self.rag.retrieve(build_rca_query(incident), k=self.top_k)
                span.set_attribute("rag.hit_count", len(evidence))

            with agent_step_span("rca", "llm.reason") as span:
                response = await self._agent().run(build_rca_prompt(incident, evidence))
                record_llm_usage(span, response)
                reasoned = _parse_reasoning(response.text)

            analysis = RootCauseAnalysis(
                org_id=incident.org_id,
                incident_id=incident_id,
                hypothesis=reasoned.hypothesis,
                confidence=reasoned.confidence,
                affected_files=reasoned.affected_files,
                evidence=[
                    RCAEvidence(source=item.source, content=item.content, score=item.score)
                    for item in evidence
                ],
                model=self._model_name(),
            )

            with agent_step_span("rca", "postgres.persist"):
                stored = await self.store.insert_root_cause_analysis(analysis)
                await self.store.insert_agent_action(
                    org_id=incident.org_id,
                    incident_id=incident_id,
                    agent_name="rca",
                    action="analyze",
                    status="succeeded",
                    output={
                        "rca_id": stored.id,
                        "confidence": stored.confidence,
                        "evidence_count": len(stored.evidence),
                    },
                )
            return stored
        except Exception as exc:
            await self._audit_failure(incident, incident_id, exc)
            raise

    async def _audit_failure(self, incident: Incident, incident_id: str, error: Exception) -> None:
        """Best-effort failure audit that never masks the original exception."""
        try:
            await self.store.insert_agent_action(
                org_id=incident.org_id,
                incident_id=incident_id,
                agent_name="rca",
                action="analyze",
                status="failed",
                output={"error_type": type(error).__name__},
            )
        except Exception:  # noqa: BLE001 — preserve the original RCA failure
            return


def _parse_reasoning(text: str) -> _ReasoningOutput:
    """Validate the model's JSON strictly; an RCA must never be fabricated silently."""
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("RCA response must be a JSON object")
        return _ReasoningOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ValueError("RCA agent returned invalid structured output") from exc
