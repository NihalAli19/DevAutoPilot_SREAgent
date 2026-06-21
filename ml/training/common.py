"""Shared training helpers: MLflow setup and a train+log routine.

Keeps each ``train_*.py`` script a thin, runnable wrapper while centralizing the
dataset load, evaluation, and experiment tracking.
"""

from __future__ import annotations

import math
from typing import Any, Protocol

import numpy as np
import pandas as pd

from config import CONFIG, ML_DIR

EXPERIMENT = "anomaly-detection"


class Detector(Protocol):
    name: str

    def fit(self, train: pd.DataFrame) -> Any: ...
    def score(self, df: pd.DataFrame) -> np.ndarray: ...


def configure_mlflow():  # noqa: ANN201 (mlflow module)
    """Point MLflow at a local SQLite tracking store under ``ml/`` (gitignored).

    MLflow 3.x put the filesystem store in maintenance mode and requires a database
    backend; SQLite keeps it free, local, and cross-platform.
    """
    import mlflow

    mlflow.set_tracking_uri(f"sqlite:///{(ML_DIR / 'mlflow.db').as_posix()}")
    mlflow.set_experiment(EXPERIMENT)
    return mlflow


def train_and_log(
    detector: Detector, params: dict[str, Any] | None = None
) -> tuple[dict[str, float], Detector]:
    """Train ``detector`` on the prepared dataset, evaluate, and log to MLflow.

    Returns ``(metrics, fitted_detector)`` so callers can persist a serving artifact.
    """
    from evaluation.evaluate import check_gate, compute_metrics
    from training.dataset import dataset_summary, prepare_datasets, using_real_nab

    mlflow = configure_mlflow()
    train, test = prepare_datasets()
    y = test["is_anomaly"].astype(int).to_numpy()

    with mlflow.start_run(run_name=detector.name):
        detector.fit(train)
        metrics = compute_metrics(y, detector.score(test))
        mlflow.log_params(
            {
                "model": detector.name,
                "feature_version": CONFIG.feature_version,
                "real_nab": using_real_nab(),
                **(params or {}),
            }
        )
        mlflow.log_metrics({k: v for k, v in metrics.items() if not math.isnan(v)})
        mlflow.log_metrics(dataset_summary(train, test))
        mlflow.set_tag("gate_pass", check_gate(metrics["pr_auc"]))
    return metrics, detector
