"""Anomaly service — loads the trained serving artifact and scores telemetry.

In-process serving (Phase 1): the FastAPI backend loads the Isolation Forest joblib
bundle produced by the ML pipeline and reuses the *same* feature code from the ``ml``
package (no train/serve skew). The heavy LSTM-AE goes to a dedicated Azure ML endpoint
in Phase 4; this service stays model-agnostic so the artifact can be swapped.
"""

# TODO(plan: Phase 4) — package `ml` properly / move heavy models to Azure ML.
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.config import get_settings

# The serving + feature code lives in the sibling `ml` package (monorepo).
_ML_DIR = Path(__file__).resolve().parents[3] / "ml"
if str(_ML_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_DIR))

from config import DEFAULT_MODEL_PATH  # noqa: E402  (ml package)
from serving.predict import Scorer, load_scorer  # noqa: E402  (ml package)


class AnomalyService:
    """Loads and serves the anomaly-scoring artifact (lazy, cached)."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        self._model_path = model_path
        self._scorer: Scorer | None = None

    @property
    def model_path(self) -> Path:
        configured = self._model_path or get_settings().anomaly_model_path
        return Path(configured) if configured else DEFAULT_MODEL_PATH

    def _scorer_or_load(self) -> Scorer:
        if self._scorer is None:
            path = self.model_path
            if not path.exists():
                raise FileNotFoundError(
                    f"anomaly model artifact not found at {path}; train it with "
                    "`python -m training.train_isolation_forest`"
                )
            self._scorer = load_scorer(path)
        return self._scorer

    def score_points(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        """Score a window of ``{timestamp, value}`` points."""
        scorer = self._scorer_or_load()
        scored = scorer.score_points(points)
        return {
            "model_name": scorer.model_name,
            "feature_version": scorer.feature_version,
            "warmup_skipped": len(points) - len(scored),
            "scored": scored,
        }
