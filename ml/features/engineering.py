"""Feature engineering — versioned features for the anomaly models.

Turns a raw NAB-shaped frame (``timestamp``, ``value``[, ``is_anomaly``]) into a
model-ready feature matrix: rolling statistics, lags, differences, a rolling
robust z-score, and cyclical time-of-day / day-of-week encodings. Bump
``FEATURE_VERSION`` whenever the feature set changes (it is logged with each model
run so scores stay comparable).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import CONFIG, MLConfig

FEATURE_VERSION = CONFIG.feature_version


def feature_columns(config: MLConfig = CONFIG) -> list[str]:
    """Deterministic ordered list of engineered feature column names."""
    cols = ["value"]
    for w in config.rolling_windows:
        cols += [f"roll_mean_{w}", f"roll_std_{w}", f"roll_z_{w}"]
    cols += [f"lag_{lag}" for lag in config.lags]
    cols += ["diff_1", "pct_change_1", "tod_sin", "tod_cos", "dow_sin", "dow_cos"]
    return cols


def build_features(df: pd.DataFrame, config: MLConfig = CONFIG) -> pd.DataFrame:
    """Build the engineered feature frame.

    Returns a frame indexed by row containing ``timestamp``, all feature columns,
    and (when present in the input) the passthrough ``is_anomaly`` label. Rows with
    NaNs introduced by rolling/lag windows are dropped so the matrix is model-ready.
    """
    if "value" not in df.columns or "timestamp" not in df.columns:
        raise ValueError("input must have 'timestamp' and 'value' columns")

    out = pd.DataFrame(
        {"timestamp": df["timestamp"].to_numpy(), "value": df["value"].to_numpy()}
    )
    value = out["value"]

    for w in config.rolling_windows:
        roll = value.rolling(window=w, min_periods=w)
        mean, std = roll.mean(), roll.std()
        out[f"roll_mean_{w}"] = mean
        out[f"roll_std_{w}"] = std
        # Robust-ish rolling z-score; guard against zero variance.
        out[f"roll_z_{w}"] = (value - mean) / std.replace(0.0, np.nan)

    for lag in config.lags:
        out[f"lag_{lag}"] = value.shift(lag)

    out["diff_1"] = value.diff(1)
    out["pct_change_1"] = value.pct_change(1, fill_method=None).replace(
        [np.inf, -np.inf], np.nan
    )

    tod = out["timestamp"].dt.hour * 60 + out["timestamp"].dt.minute
    out["tod_sin"] = np.sin(2 * np.pi * tod / (24 * 60))
    out["tod_cos"] = np.cos(2 * np.pi * tod / (24 * 60))
    dow = out["timestamp"].dt.dayofweek
    out["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    out["dow_cos"] = np.cos(2 * np.pi * dow / 7)

    if "is_anomaly" in df.columns:
        out["is_anomaly"] = df["is_anomaly"].to_numpy()

    return out.dropna().reset_index(drop=True)


def split_xy(
    features: pd.DataFrame, config: MLConfig = CONFIG
) -> tuple[pd.DataFrame, pd.Series | None]:
    """Split an engineered frame into the feature matrix X and labels y (if any)."""
    x = features[feature_columns(config)].copy()
    y = features["is_anomaly"].astype(int) if "is_anomaly" in features.columns else None
    return x, y
