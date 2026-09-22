"""Reliability Guard: assess post-merge health without executing production actions."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

from agent_framework import Agent
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import Settings, get_settings
from app.models.incident import Incident
from app.models.patch import PatchProposal
from app.models.reliability import (
    PullRequestStatus,
    ReliabilityAssessment,
    RolloutHealth,
    TimeWindow,
)
from app.services import db_service
from app.services.github_service import GitHubService
from app.services.health_service import HealthService
from app.services.llm_router import LLMRouter
from app.utils.prompts import RELIABILITY_INSTRUCTIONS, build_reliability_prompt
from app.utils.telemetry import agent_step_span, record_llm_usage

Decision = Literal["approve", "rollback", "escalate"]
_UTC = ZoneInfo("UTC")


class MergeEvidenceSource(Protocol):
    async def get_pull_request(self, number: int) -> PullRequestStatus: ...


class HealthReader(Protocol):
    async def compare(
        self,
        *,
        org_id: str,
        service: str,
        baseline_window: TimeWindow,
        current_window: TimeWindow,
    ) -> RolloutHealth: ...


class ReliabilityStore(Protocol):
    async def mark_patch_merged(
        self,
        *,
        org_id: str,
        patch_id: str,
        approved_by: str,
        approved_at: datetime,
    ) -> PatchProposal: ...

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
    model_config = ConfigDict(extra="forbid")

    decision: Decision
    rationale: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)


class ReliabilityAgent:
    """Produce an auditable recommendation after a verified human merge."""

    def __init__(
        self,
        *,
        repository: MergeEvidenceSource | None = None,
        health_service: HealthReader | None = None,
        chat_client: Any | None = None,
        llm_router: LLMRouter | None = None,
        store: ReliabilityStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if (
            self.settings.guard_rollback_regression_ratio
            < self.settings.guard_escalate_regression_ratio
        ):
            raise ValueError("rollback threshold must be at least the escalation threshold")
        self.repository = repository or GitHubService(self.settings)
        self.health = health_service or HealthService(
            minimum_samples=self.settings.guard_min_samples
        )
        self._chat_client = chat_client
        self.router = llm_router or LLMRouter(settings=self.settings)
        self.store = store or db_service

    def _agent(self) -> Agent:
        client = self._chat_client or self.router.chat_client(
            provider=self.settings.guard_llm_provider
        )
        return Agent(client, instructions=RELIABILITY_INSTRUCTIONS, name="reliability")

    def _model_name(self) -> str:
        provider = self.settings.guard_llm_provider
        if provider == "ollama":
            return self.settings.ollama_model
        if provider == "azure":
            return self.settings.azure_openai_deployment or self.settings.llm_cloud_model
        return self.settings.llm_cloud_model

    async def assess(
        self,
        *,
        incident_id: str,
        incident: Incident,
        patch: PatchProposal,
        baseline_window: TimeWindow,
        current_window: TimeWindow,
    ) -> ReliabilityAssessment:
        """Verify the merge, compare health, and persist a recommendation-only decision."""
        try:
            _validate_patch_scope(incident_id, incident, patch)
            with agent_step_span("reliability", "github.verify_human_merge") as span:
                pull = await self.repository.get_pull_request(patch.pr_number or 0)
                _validate_human_merge(pull)
                if pull.number != patch.pr_number:
                    raise ValueError("GitHub returned merge evidence for the wrong pull request")
                assert pull.merged_at is not None
                assert pull.merged_by is not None
                _validate_rollout_windows(baseline_window, current_window, pull.merged_at)
                span.set_attribute("github.pr_number", pull.number)
                span.set_attribute("github.merged_by", pull.merged_by)

            with agent_step_span("reliability", "postgres.record_merge"):
                await self.store.mark_patch_merged(
                    org_id=incident.org_id,
                    patch_id=patch.id or "",
                    approved_by=pull.merged_by,
                    approved_at=pull.merged_at,
                )

            with agent_step_span("reliability", "postgres.compare_health") as span:
                health = await self.health.compare(
                    org_id=incident.org_id,
                    service=incident.service,
                    baseline_window=baseline_window,
                    current_window=current_window,
                )
                span.set_attribute("health.metric_count", len(health.metrics))
                span.set_attribute("health.sufficient_data", health.sufficient_data)
                span.set_attribute("health.worst_regression_ratio", health.worst_regression_ratio)

            assessment = await self._decide(incident_id, incident, patch, health)
            with agent_step_span("reliability", "postgres.persist_recommendation"):
                await self.store.insert_agent_action(
                    org_id=incident.org_id,
                    incident_id=incident_id,
                    agent_name="reliability",
                    action="assess_rollout",
                    status="succeeded",
                    output=assessment.model_dump(mode="json"),
                )
            return assessment
        except Exception as exc:
            await self._audit_failure(incident, incident_id, exc)
            raise

    async def _decide(
        self,
        incident_id: str,
        incident: Incident,
        patch: PatchProposal,
        health: RolloutHealth,
    ) -> ReliabilityAssessment:
        hard_decision = self._hard_gate(health)
        model: str | None = None
        if hard_decision is None:
            with agent_step_span("reliability", "llm.assess") as span:
                response = await self._agent().run(build_reliability_prompt(health))
                record_llm_usage(span, response)
                reasoned = _parse_reasoning(response.text)
            decision, rationale, confidence = self._apply_safety_overrides(reasoned, health)
            model = self._model_name()
        else:
            decision, rationale, confidence = hard_decision

        return ReliabilityAssessment(
            org_id=incident.org_id,
            incident_id=incident_id,
            patch_id=patch.id or "",
            service=incident.service,
            decision=decision,
            rationale=rationale,
            confidence=confidence,
            health=health,
            requires_human_approval=decision in {"rollback", "escalate"},
            model=model,
            created_at=datetime.now(_UTC),
        )

    def _hard_gate(self, health: RolloutHealth) -> tuple[Decision, str, float] | None:
        if not health.sufficient_data:
            details = ", ".join(health.missing_or_unsupported_metrics) or "sample counts"
            return (
                "escalate",
                f"Insufficient rollout evidence ({details}); human investigation is required.",
                1.0,
            )
        if health.worst_regression_ratio >= self.settings.guard_rollback_regression_ratio:
            return (
                "rollback",
                "Deterministic health gate detected a severe regression; rollback requires "
                "explicit human approval.",
                1.0,
            )
        return None

    def _apply_safety_overrides(
        self,
        reasoned: _ReasoningOutput,
        health: RolloutHealth,
    ) -> tuple[Decision, str, float]:
        decision = reasoned.decision
        if decision not in {"approve", "rollback", "escalate"}:
            raise ValueError("Reliability Guard returned an invalid decision")
        rationale = reasoned.rationale.strip()
        if not rationale:
            raise ValueError("Reliability Guard rationale must not be blank")
        confidence = reasoned.confidence

        if confidence < self.settings.guard_min_confidence:
            return (
                "escalate",
                "Model confidence is below the configured threshold; human investigation "
                "is required.",
                confidence,
            )
        if (
            decision == "approve"
            and health.worst_regression_ratio >= self.settings.guard_escalate_regression_ratio
        ):
            return (
                "escalate",
                "The model recommended approval despite a material deterministic health "
                "regression; human investigation is required.",
                confidence,
            )
        return decision, rationale, confidence

    async def _audit_failure(self, incident: Incident, incident_id: str, error: Exception) -> None:
        try:
            await self.store.insert_agent_action(
                org_id=incident.org_id,
                incident_id=incident_id,
                agent_name="reliability",
                action="assess_rollout",
                status="failed",
                output={"error_type": type(error).__name__},
            )
        except Exception:  # noqa: BLE001 - preserve the original Guard failure
            return


def _validate_patch_scope(incident_id: str, incident: Incident, patch: PatchProposal) -> None:
    if patch.org_id != incident.org_id or patch.incident_id != incident_id:
        raise ValueError("patch does not belong to this incident and tenant")
    if not patch.id or not patch.pr_number:
        raise ValueError("patch must be persisted and linked to a pull request")
    if patch.status == "rejected":
        raise ValueError("a rejected patch cannot be assessed")


def _validate_human_merge(pull: PullRequestStatus) -> None:
    if pull.draft or not pull.merged or pull.merged_at is None:
        raise ValueError("pull request must be human-approved and merged before assessment")
    if (
        not pull.merged_by
        or pull.merged_by_type != "User"
        or pull.merged_by.lower().endswith("[bot]")
    ):
        raise ValueError("pull request merge was not performed by a human user")


def _validate_rollout_windows(
    baseline: TimeWindow,
    current: TimeWindow,
    merged_at: datetime,
) -> None:
    if baseline.end > merged_at:
        raise ValueError("baseline window must end no later than the verified merge")
    if current.start < merged_at:
        raise ValueError("post-deployment window must start at or after the verified merge")


def _parse_reasoning(text: str) -> _ReasoningOutput:
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Reliability Guard response must be a JSON object")
        return _ReasoningOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ValueError("Reliability Guard returned invalid structured output") from exc
