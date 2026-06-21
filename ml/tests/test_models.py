"""Phase 1 slice 2 tests: detectors, metrics, gate, and the comparison runner.

Kept fast (small synthetic series, tiny LSTM) so they run in CI; full training on
real NAB happens locally / in the ML pipeline workflow.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.synthetic import generate
from evaluation.evaluate import (
    check_gate,
    compute_metrics,
    format_table,
    pick_best,
    run_comparison,
)
from features.engineering import build_features
from training.detectors import IsolationForestDetector, RobustZScoreDetector
from training.lstm_ae import LSTMAutoencoderDetector


def _features() -> pd.DataFrame:
    return build_features(generate(n_points=1400, n_anomalies=12, seed=11))


# --------------------------------------------------------------------------- #
# Metrics / gate
# --------------------------------------------------------------------------- #


def test_compute_metrics_perfect_separation():
    m = compute_metrics([0, 0, 0, 1, 1], [0.1, 0.2, 0.3, 0.9, 1.0])
    assert m["pr_auc"] == 1.0
    assert m["f1"] > 0.99


def test_compute_metrics_handles_degenerate_labels():
    assert np.isnan(compute_metrics([0, 0, 0], [0.1, 0.2, 0.3])["pr_auc"])
    assert np.isnan(compute_metrics([1, 1, 1], [0.1, 0.2, 0.3])["pr_auc"])


def test_pick_best_and_gate():
    results = {
        "a": {"pr_auc": 0.40, "precision": 0, "recall": 0, "f1": 0, "threshold": 0},
        "b": {"pr_auc": 0.82, "precision": 0, "recall": 0, "f1": 0, "threshold": 0},
    }
    assert pick_best(results) == "b"
    assert check_gate(0.82, 0.70)
    assert not check_gate(0.55, 0.70)
    assert not check_gate(float("nan"), 0.70)


def test_format_table_lists_all_models():
    table = format_table({"m1": compute_metrics([0, 1], [0.1, 0.9])})
    assert "PR-AUC" in table and "m1" in table


# --------------------------------------------------------------------------- #
# Detectors
# --------------------------------------------------------------------------- #


def test_detectors_score_shape_and_finite():
    feats = _features()
    train = feats.iloc[: len(feats) // 2].reset_index(drop=True)
    test = feats.iloc[len(feats) // 2 :].reset_index(drop=True)
    detectors = [
        RobustZScoreDetector(),
        IsolationForestDetector(n_estimators=50),
        LSTMAutoencoderDetector(seq_len=16, hidden=16, latent=8, epochs=3),
    ]
    for det in detectors:
        scores = det.fit(train).score(test)
        assert len(scores) == len(test)
        assert np.isfinite(scores).all()


def test_classical_detectors_beat_random_base_rate():
    # Injected anomalies are large; fit on the first half, score the full series so
    # both classes are present, and require beating the positive base rate (~random AP).
    feats = _features()
    train = feats.iloc[: len(feats) // 2].reset_index(drop=True)
    y = feats["is_anomaly"].astype(int).to_numpy()
    assert y.sum() > 0 and (y == 0).sum() > 0
    for det in [RobustZScoreDetector(), IsolationForestDetector(n_estimators=100)]:
        m = compute_metrics(y, det.fit(train).score(feats))
        assert m["pr_auc"] >= y.mean()


def test_lstm_detector_requires_fit():
    import pytest

    with pytest.raises(RuntimeError):
        LSTMAutoencoderDetector().score(_features())


# --------------------------------------------------------------------------- #
# Comparison runner (uses the vendored sample, tiny LSTM)
# --------------------------------------------------------------------------- #


def test_run_comparison_returns_all_three():
    out = run_comparison(use_real=False, lstm_epochs=2)
    assert set(out["results"]) == {
        "robust_zscore",
        "isolation_forest",
        "lstm_autoencoder",
    }
    for m in out["results"].values():
        assert set(m) == {"pr_auc", "precision", "recall", "f1", "threshold"}
