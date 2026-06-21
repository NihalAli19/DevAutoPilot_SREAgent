"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

# Make the sibling `ml` package importable (feature pipeline + serving code).
_ML_DIR = Path(__file__).resolve().parents[2] / "ml"
if str(_ML_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_DIR))

from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Async HTTP client wired to the FastAPI app via ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def if_artifact(tmp_path):
    """Train a tiny Isolation Forest on synthetic data and save a serving artifact."""
    from data.synthetic import generate
    from features.engineering import build_features
    from serving.predict import save_sklearn_artifact
    from training.detectors import IsolationForestDetector

    feats = build_features(generate(n_points=900, n_anomalies=6, seed=3))
    det = IsolationForestDetector(n_estimators=40).fit(feats)
    path = tmp_path / "if.joblib"
    save_sklearn_artifact(det.model, det.scaler, det.cols, 0.0, det.name, path)
    return path
