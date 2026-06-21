"""Evaluation: precision/recall/F1/PR-AUC, model comparison, and the eval gate.

Anomaly detectors emit a continuous score; we report PR-AUC (threshold-free) plus
the precision/recall/F1 at the F1-optimal threshold. ``run_comparison`` trains all
three detectors and returns a side-by-side table; ``check_gate`` is the regression
guard wired into CI via ``.github/workflows/ml-pipeline.yml`` (``main`` exits non-zero
when the best model regresses below the floor).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve

from config import ARTIFACTS_DIR, CONFIG

Metrics = dict[str, float]


def compute_metrics(y_true: Sequence[int], scores: Sequence[float]) -> Metrics:
    """PR-AUC plus precision/recall/F1 at the F1-optimal threshold."""
    y = np.asarray(y_true).astype(int)
    s = np.asarray(scores, dtype=float)
    if y.sum() == 0 or y.sum() == len(y):
        return {
            "pr_auc": float("nan"),
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "threshold": 0.0,
        }
    pr_auc = float(average_precision_score(y, s))
    precision, recall, thresholds = precision_recall_curve(y, s)
    f1 = 2 * precision * recall / (precision + recall + 1e-12)
    best = int(np.argmax(f1))
    threshold = (
        float(thresholds[min(best, len(thresholds) - 1)]) if len(thresholds) else 0.0
    )
    return {
        "pr_auc": pr_auc,
        "precision": float(precision[best]),
        "recall": float(recall[best]),
        "f1": float(f1[best]),
        "threshold": threshold,
    }


def pick_best(results: Mapping[str, Metrics]) -> str:
    """Name of the model with the highest PR-AUC (NaN treated as -inf)."""

    def key(name: str) -> float:
        v = results[name]["pr_auc"]
        return -np.inf if np.isnan(v) else v

    return max(results, key=key)


def check_gate(pr_auc: float, floor: float = CONFIG.pr_auc_floor) -> bool:
    """True iff PR-AUC clears the gate floor (the CI regression guard)."""
    return bool(not np.isnan(pr_auc) and pr_auc >= floor)


def format_table(results: Mapping[str, Metrics]) -> str:
    """Render a side-by-side comparison table (markdown)."""
    header = "| Model | Precision | Recall | F1 | PR-AUC |\n|:--|--:|--:|--:|--:|"
    rows = [
        f"| {name} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['pr_auc']:.3f} |"
        for name, m in results.items()
    ]
    return "\n".join([header, *rows])


def run_comparison(
    train_frac: float = 0.5, use_real: bool = True, lstm_epochs: int = 12
) -> dict:
    """Train all three detectors and return their metrics + dataset summary."""
    from training.dataset import dataset_summary, prepare_datasets, using_real_nab
    from training.detectors import IsolationForestDetector, RobustZScoreDetector
    from training.lstm_ae import LSTMAutoencoderDetector

    train, test = prepare_datasets(train_frac=train_frac, use_real=use_real)
    y = test["is_anomaly"].astype(int).to_numpy()

    detectors = [
        RobustZScoreDetector(),
        IsolationForestDetector(),
        LSTMAutoencoderDetector(epochs=lstm_epochs),
    ]
    results: dict[str, Metrics] = {}
    for det in detectors:
        det.fit(train)
        results[det.name] = compute_metrics(y, det.score(test))

    return {
        "results": results,
        "summary": dataset_summary(train, test),
        "real_nab": using_real_nab(),
    }


def main() -> int:
    """Train + evaluate; print the comparison table and enforce the gate.

    Returns process exit code: 0 if the best model clears the PR-AUC floor, 1 if it
    regresses below it (this is the CI eval gate that blocks a bad model).
    """
    out = run_comparison()
    print(format_table(out["results"]))
    best = pick_best(out["results"])
    best_pr_auc = out["results"][best]["pr_auc"]
    passed = check_gate(best_pr_auc)
    print(f"\nBest model: {best} (PR-AUC {best_pr_auc:.3f})")
    print(f"Gate (floor {CONFIG.pr_auc_floor:.2f}): {'PASS' if passed else 'FAIL'}")
    print(
        f"Data: {'real NAB' if out['real_nab'] else 'vendored sample'} | {out['summary']}"
    )

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "metrics.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )

    if not passed:
        print(
            f"GATE FAILED: best PR-AUC {best_pr_auc:.3f} < floor {CONFIG.pr_auc_floor:.2f}"
        )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
