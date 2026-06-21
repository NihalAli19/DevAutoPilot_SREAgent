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


_SCHEMA_SQL = (Path(__file__).resolve().parents[2] / "db" / "schema.sql").read_text(
    encoding="utf-8"
)


@pytest_asyncio.fixture
async def db():
    """Apply the schema to the configured Postgres and truncate between tests.

    Skips (not fails) when no Postgres is reachable, so non-DB environments still run
    the rest of the suite; CI provisions a Postgres service for these tests.
    """
    import asyncpg

    from app.config import get_settings
    from app.services.db_service import dispose_engine

    dsn = get_settings().database_url.replace("+asyncpg", "")
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable ({exc}); set DATABASE_URL to run DB tests")
    try:
        await conn.execute(_SCHEMA_SQL)
        await conn.execute("TRUNCATE incidents, agent_actions RESTART IDENTITY CASCADE")
    finally:
        await conn.close()
    yield
    await dispose_engine()


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
