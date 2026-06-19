"""Dataset loader — parse NAB time series and apply labeled anomaly windows.

NAB stores each series as a 2-column CSV (``timestamp,value``) and keeps anomaly
labels separately as a JSON map of ``"<category>/<file>" -> [[start, end], ...]``
window pairs. This module loads a series, attaches a boolean ``is_anomaly`` column
from those windows, and exposes the small vendored sample used by tests/CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import SAMPLE_DIR, SAMPLE_LABELS, SAMPLE_SERIES, SAMPLE_SERIES_KEY

Window = tuple[str, str]


def load_series(csv_path: str | Path) -> pd.DataFrame:
    """Load a NAB CSV into a sorted frame with parsed ``timestamp`` and ``value``."""
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    if list(df.columns) != ["timestamp", "value"]:
        raise ValueError(f"unexpected NAB columns {list(df.columns)} in {csv_path}")
    return df.sort_values("timestamp").reset_index(drop=True)


def apply_labels(df: pd.DataFrame, windows: list[Window]) -> pd.DataFrame:
    """Return a copy of ``df`` with a boolean ``is_anomaly`` column from windows."""
    out = df.copy()
    is_anom = pd.Series(False, index=out.index)
    for start, end in windows:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        is_anom |= out["timestamp"].between(start_ts, end_ts)
    out["is_anomaly"] = is_anom
    return out


def load_labels(labels_path: str | Path, key: str) -> list[Window]:
    """Read a NAB combined-windows JSON and return the windows for ``key``."""
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    return [(w[0], w[1]) for w in labels.get(key, [])]


def load_labeled_series(
    csv_path: str | Path, labels_path: str | Path, key: str
) -> pd.DataFrame:
    """Load a series and attach its anomaly labels in one step."""
    return apply_labels(load_series(csv_path), load_labels(labels_path, key))


def load_nab_sample() -> pd.DataFrame:
    """Load the committed NAB sample slice with labels applied (used by tests/CI)."""
    return load_labeled_series(
        SAMPLE_DIR / SAMPLE_SERIES,
        SAMPLE_DIR / SAMPLE_LABELS,
        SAMPLE_SERIES_KEY,
    )
