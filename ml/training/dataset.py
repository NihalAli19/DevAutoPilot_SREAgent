"""Assemble train/eval datasets from real NAB series (falls back to the sample).

Each series is feature-engineered, then split by time (train = earlier portion,
mostly normal; test = later portion containing the labeled anomalies). Series are
concatenated so the models see a single combined train/test matrix. We use the two
5-minute ``realAWSCloudwatch`` series so the cadence (and therefore the rolling/lag
features) is consistent.
"""

from __future__ import annotations


import pandas as pd

from config import RAW_DIR, SAMPLE_SERIES
from data.loader import load_labeled_series, load_nab_sample
from features.engineering import build_features

# Real NAB series used for training when present in RAW_DIR (5-min cadence).
NAB_SERIES: dict[str, str] = {
    "ec2_cpu_utilization_5f5533.csv": "realAWSCloudwatch/ec2_cpu_utilization_5f5533.csv",
    "ec2_network_in_5abac7.csv": "realAWSCloudwatch/ec2_network_in_5abac7.csv",
}


def _time_split(
    feats: pd.DataFrame, train_frac: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    k = int(len(feats) * train_frac)
    train = feats.iloc[:k].reset_index(drop=True)
    test = feats.iloc[k:].reset_index(drop=True)
    return train, test


def series_features(use_real: bool = True) -> list[tuple[str, pd.DataFrame]]:
    """Return ``(name, engineered_features)`` for each available series.

    Uses the full real NAB series from ``RAW_DIR`` when downloaded; otherwise falls
    back to the committed sample slice so the pipeline still runs in CI/offline.
    """
    labels_path = RAW_DIR / "combined_windows.json"
    frames: list[tuple[str, pd.DataFrame]] = []
    if use_real and labels_path.exists():
        for fname, key in NAB_SERIES.items():
            csv = RAW_DIR / fname
            if csv.exists():
                df = load_labeled_series(csv, labels_path, key)
                frames.append((fname, build_features(df)))
    if not frames:
        frames.append((SAMPLE_SERIES, build_features(load_nab_sample())))
    return frames


def prepare_datasets(
    train_frac: float = 0.5, use_real: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Concatenate per-series train/test splits into combined feature frames."""
    trains, tests = [], []
    for _name, feats in series_features(use_real=use_real):
        tr, te = _time_split(feats, train_frac)
        trains.append(tr)
        tests.append(te)
    train = pd.concat(trains, ignore_index=True)
    test = pd.concat(tests, ignore_index=True)
    return train, test


def dataset_summary(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, float]:
    """Small descriptive summary for logging."""
    return {
        "train_rows": float(len(train)),
        "test_rows": float(len(test)),
        "test_anomaly_rate": float(test["is_anomaly"].mean()) if len(test) else 0.0,
    }


def using_real_nab() -> bool:
    """True when the full real NAB series are available locally (not the sample)."""
    return (RAW_DIR / "combined_windows.json").exists() and any(
        (RAW_DIR / f).exists() for f in NAB_SERIES
    )
