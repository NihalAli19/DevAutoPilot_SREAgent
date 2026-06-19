"""Central ML config: paths, feature params, and the eval gate threshold."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # full datasets (gitignored)
SAMPLE_DIR = DATA_DIR / "sample"  # small vendored slice (committed)
PROCESSED_DIR = DATA_DIR / "processed"  # gitignored
ARTIFACTS_DIR = ML_DIR / "artifacts"  # local model artifacts (gitignored)

# The vendored NAB sample used by tests/CI (a real slice of NAB realAWSCloudwatch).
SAMPLE_SERIES = "ec2_cpu_utilization_5f5533.csv"
SAMPLE_LABELS = "combined_windows.json"
# NAB keys series by "<category>/<file>"; the sample keeps the original key.
SAMPLE_SERIES_KEY = f"realAWSCloudwatch/{SAMPLE_SERIES}"

# NAB realAWSCloudwatch is sampled every 5 minutes -> 288 points per day.
POINTS_PER_DAY = 288


@dataclass(frozen=True)
class MLConfig:
    """Feature-engineering + evaluation parameters (versioned)."""

    feature_version: str = "v1"
    seed: int = 42

    # Rolling-window sizes in points (1h, 4h, 1 day at 5-min cadence).
    rolling_windows: tuple[int, ...] = (12, 48, POINTS_PER_DAY)
    # Autoregressive lags in points.
    lags: tuple[int, ...] = (1, 2, 3, 12)

    # Eval gate: initial PR-AUC floor. Per plan, after the first real run we reset
    # this to ~0.05 below the best achieved score so it acts as a regression guard
    # rather than a trivially-passable bar.
    pr_auc_floor: float = 0.70
    gate_margin: float = 0.05

    seasonal_periods: tuple[int, ...] = field(default=(POINTS_PER_DAY,))


CONFIG = MLConfig()
