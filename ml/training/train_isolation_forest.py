"""Train the Isolation Forest detector and log the run to MLflow."""

from __future__ import annotations

from config import DEFAULT_MODEL_PATH
from serving.predict import save_sklearn_artifact
from training.common import train_and_log
from training.detectors import IsolationForestDetector


def main() -> None:
    metrics, det = train_and_log(IsolationForestDetector(), {"n_estimators": 200})
    save_sklearn_artifact(
        det.model,
        det.scaler,
        det.cols,
        metrics["threshold"],
        det.name,
        DEFAULT_MODEL_PATH,
    )
    print("isolation_forest:", metrics, "-> saved", DEFAULT_MODEL_PATH)


if __name__ == "__main__":
    main()
