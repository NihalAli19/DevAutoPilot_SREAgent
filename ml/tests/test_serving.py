"""Phase 1 slice 3 tests: serving artifact save/load + scoring raw windows."""

from __future__ import annotations

from data.synthetic import generate
from features.engineering import build_features
from serving.predict import load_scorer, save_sklearn_artifact
from training.detectors import IsolationForestDetector


def _artifact(tmp_path, threshold=0.0):
    feats = build_features(generate(n_points=1000, n_anomalies=8, seed=5))
    det = IsolationForestDetector(n_estimators=50).fit(feats)
    path = tmp_path / "if.joblib"
    save_sklearn_artifact(det.model, det.scaler, det.cols, threshold, det.name, path)
    return path


def test_save_load_roundtrip(tmp_path):
    scorer = load_scorer(_artifact(tmp_path))
    assert scorer.model_name == "isolation_forest"
    assert scorer.feature_columns
    assert isinstance(scorer.threshold, float)


def test_score_points_shape_and_types(tmp_path):
    scorer = load_scorer(_artifact(tmp_path))
    df = generate(n_points=450, n_anomalies=3, seed=6)
    points = [
        {"timestamp": t.isoformat(), "value": float(v)}
        for t, v in zip(df["timestamp"], df["value"])
    ]
    out = scorer.score_points(points)
    assert len(out) > 0  # tail rows survive warm-up
    assert len(out) < len(points)  # warm-up rows dropped
    for row in out:
        assert set(row) == {"timestamp", "value", "anomaly_score", "is_anomaly"}
        assert isinstance(row["anomaly_score"], float)
        assert isinstance(row["is_anomaly"], bool)


def test_threshold_controls_flags(tmp_path):
    # An impossibly high threshold flags nothing; a very low one flags everything.
    df = generate(n_points=450, seed=7)
    points = [
        {"timestamp": t.isoformat(), "value": float(v)}
        for t, v in zip(df["timestamp"], df["value"])
    ]
    hi = load_scorer(_artifact(tmp_path, threshold=1e9)).score_points(points)
    lo = load_scorer(_artifact(tmp_path, threshold=-1e9)).score_points(points)
    assert not any(r["is_anomaly"] for r in hi)
    assert all(r["is_anomaly"] for r in lo)
