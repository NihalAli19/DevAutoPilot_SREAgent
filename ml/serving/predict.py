"""Serving: persist a trained detector as a portable artifact and score telemetry.

The artifact bundles everything needed to score (model + scaler + feature column
list + feature version + decision threshold) so the FastAPI backend can load it and
serve ``/score`` in-process, reusing the *exact* training feature pipeline (no
train/serve skew). Scoring rebuilds features, so callers send a window of raw points.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from config import CONFIG
from features.engineering import build_features


def save_sklearn_artifact(
    model: Any,
    scaler: Any,
    feature_columns: list[str],
    threshold: float,
    name: str,
    path: Path,
) -> Path:
    """Persist a sklearn-style detector (with ``score_samples``) as one joblib file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "scaler": scaler,
            "feature_columns": feature_columns,
            "feature_version": CONFIG.feature_version,
            "threshold": float(threshold),
            "model_name": name,
        },
        path,
    )
    return path


@dataclass
class Scorer:
    """Loaded scoring artifact: rebuilds features and scores raw telemetry windows."""

    model: Any
    scaler: Any
    feature_columns: list[str]
    feature_version: str
    threshold: float
    model_name: str

    def score_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score a NAB-shaped frame; returns scored rows (warm-up rows dropped)."""
        feats = build_features(df)
        if feats.empty:
            return feats.assign(anomaly_score=[], is_anomaly=[])
        x = self.scaler.transform(feats[self.feature_columns])
        scores = -self.model.score_samples(x)  # higher = more anomalous
        out = feats[["timestamp", "value"]].copy()
        out["anomaly_score"] = scores
        out["is_anomaly"] = scores >= self.threshold
        return out

    def score_points(self, points: list[dict]) -> list[dict]:
        """Score a window of ``{timestamp, value}`` points; returns scored tail rows."""
        df = pd.DataFrame(points)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["value"] = df["value"].astype(float)
        scored = self.score_frame(df.sort_values("timestamp").reset_index(drop=True))
        return [
            {
                "timestamp": ts.isoformat(),
                "value": float(v),
                "anomaly_score": float(s),
                "is_anomaly": bool(a),
            }
            for ts, v, s, a in zip(
                scored["timestamp"],
                scored["value"],
                scored["anomaly_score"],
                scored["is_anomaly"],
            )
        ]


def load_scorer(path: str | Path) -> Scorer:
    """Load a serving artifact saved by :func:`save_sklearn_artifact`."""
    bundle = joblib.load(path)
    return Scorer(
        model=bundle["model"],
        scaler=bundle["scaler"],
        feature_columns=bundle["feature_columns"],
        feature_version=bundle["feature_version"],
        threshold=bundle["threshold"],
        model_name=bundle["model_name"],
    )
