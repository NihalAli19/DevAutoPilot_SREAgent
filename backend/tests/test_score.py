"""Tests for the in-process anomaly scoring service and POST /api/score."""

import pytest

from app.api import score as score_module
from app.services.anomaly_service import AnomalyService


def _points(n: int = 450, seed: int = 6) -> list[dict]:
    from data.synthetic import generate  # ml package (on path via conftest)

    df = generate(n_points=n, seed=seed)
    return [
        {"timestamp": t.isoformat(), "value": float(v)}
        for t, v in zip(df["timestamp"], df["value"], strict=False)
    ]


def test_anomaly_service_scores(if_artifact):
    svc = AnomalyService(model_path=if_artifact)
    result = svc.score_points(_points())
    assert result["model_name"] == "isolation_forest"
    assert result["scored"]
    assert result["warmup_skipped"] > 0


@pytest.mark.asyncio
async def test_score_endpoint(client, if_artifact, monkeypatch):
    monkeypatch.setattr(score_module, "_service", AnomalyService(model_path=if_artifact))
    resp = await client.post("/api/score", json={"points": _points()})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_name"] == "isolation_forest"
    assert len(body["scored"]) > 0
    assert {"timestamp", "value", "anomaly_score", "is_anomaly"} == set(body["scored"][0])


@pytest.mark.asyncio
async def test_score_endpoint_missing_model_returns_503(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        score_module, "_service", AnomalyService(model_path=tmp_path / "nope.joblib")
    )
    resp = await client.post(
        "/api/score", json={"points": [{"timestamp": "2024-01-01T00:00:00", "value": 1.0}]}
    )
    assert resp.status_code == 503
