"""Anomaly service — loads the trained model and scores telemetry."""
# TODO(plan: Phase 1) — load Isolation Forest / LSTM-AE and expose scoring.


class AnomalyService:
    """Serves anomaly scores to the Monitoring Agent (ML gates the LLM)."""
