"""Monitoring Agent — calls the anomaly endpoint, then LLM-classifies severity."""
# TODO(plan: Phase 2) — ML-gates-LLM: anomaly score -> severity/type classification.


class MonitoringAgent:
    """Detects anomalies and dispatches structured incidents."""
