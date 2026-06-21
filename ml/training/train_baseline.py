"""Train the robust z-score baseline detector and log the run to MLflow."""

from __future__ import annotations

from training.common import train_and_log
from training.detectors import RobustZScoreDetector


def main() -> None:
    det = RobustZScoreDetector()
    metrics = train_and_log(det, {"window": det.window})
    print("robust_zscore:", metrics)


if __name__ == "__main__":
    main()
