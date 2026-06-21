"""Train the Isolation Forest detector and log the run to MLflow."""

from __future__ import annotations

from training.common import train_and_log
from training.detectors import IsolationForestDetector


def main() -> None:
    metrics = train_and_log(IsolationForestDetector(), {"n_estimators": 200})
    print("isolation_forest:", metrics)


if __name__ == "__main__":
    main()
