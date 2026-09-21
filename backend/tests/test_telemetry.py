"""Tests for vendor-neutral OpenTelemetry agent helpers."""

from types import SimpleNamespace
from typing import Any, cast

from opentelemetry.trace import Span

from app.utils.telemetry import record_llm_usage


class RecordingSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, name: str, value: Any) -> None:
        self.attributes[name] = value


def test_record_llm_usage_reads_agent_framework_mapping():
    span = RecordingSpan()
    response = SimpleNamespace(usage_details={"input_token_count": 120, "output_token_count": 35})

    record_llm_usage(cast(Span, span), response)

    assert span.attributes == {
        "llm.usage.reported": True,
        "llm.tokens.input": 120,
        "llm.tokens.output": 35,
    }
