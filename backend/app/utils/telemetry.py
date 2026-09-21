"""OpenTelemetry helpers for agent steps.

The API dependency is vendor-neutral. Phase 4 will configure an Azure Monitor exporter;
until then the default no-op provider keeps local development and tests dependency-free.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span

_TRACER = trace.get_tracer("devautopilot.agents")


@contextmanager
def agent_step_span(agent_name: str, tool: str) -> Iterator[Span]:
    """Emit a timed span for one agent tool/step."""
    started = perf_counter()
    with _TRACER.start_as_current_span(f"agent.{agent_name}.{tool}") as span:
        span.set_attribute("agent.name", agent_name)
        span.set_attribute("agent.tool", tool)
        try:
            yield span
        finally:
            span.set_attribute("agent.latency_ms", (perf_counter() - started) * 1000)


def record_llm_usage(span: Span, response: Any) -> None:
    """Attach token counts when the Agent Framework response reports them."""
    usage = getattr(response, "usage_details", None)
    if isinstance(usage, Mapping):
        input_tokens = usage.get("input_token_count")
        output_tokens = usage.get("output_token_count")
    else:
        input_tokens = getattr(usage, "input_token_count", None)
        output_tokens = getattr(usage, "output_token_count", None)
    span.set_attribute("llm.usage.reported", usage is not None)
    if input_tokens is not None:
        span.set_attribute("llm.tokens.input", int(input_tokens))
    if output_tokens is not None:
        span.set_attribute("llm.tokens.output", int(output_tokens))
