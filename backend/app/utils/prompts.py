"""Prompt templates for the agent workflow."""

# TODO(plan: Phase 3) — add RCA / Patch / Postmortem prompts.
from __future__ import annotations

from typing import Any

MONITORING_INSTRUCTIONS = (
    "You are an SRE Monitoring Agent. A trained anomaly-detection model has ALREADY "
    "flagged this telemetry as anomalous; your job is to classify the incident. "
    "Respond with ONLY a JSON object and no prose:\n"
    '{"severity": "P1|P2|P3|P4", "type": "<short category, e.g. latency, error_rate, '
    'throughput, resource>", "title": "<concise incident title>", '
    '"summary": "<one-sentence explanation>", "confidence": <number 0..1>}\n'
    "Severity: P1 = critical/outage, P2 = major, P3 = moderate, P4 = minor."
)


def build_monitoring_prompt(
    service: str,
    metric: str,
    scored: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    peak: dict[str, Any],
) -> str:
    """Summarize the anomalous window for the LLM to classify."""
    n = len(scored)
    a = len(anomalies)
    rate = (a / n) if n else 0.0
    return (
        f"Service: {service}\n"
        f"Metric: {metric}\n"
        f"Window: {n} points, {a} anomalous ({rate:.0%}).\n"
        f"Peak anomaly score {peak['anomaly_score']:.3f} at {peak['timestamp']} "
        f"(value={peak['value']:.3f}).\n"
        "Classify this incident as instructed."
    )
