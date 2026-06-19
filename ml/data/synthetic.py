"""Synthetic generator — seasonal series with injected anomalies for demos/tests.

Produces a NAB-shaped frame (``timestamp``, ``value``, ``is_anomaly``) so the same
loader/feature code works on it. Used to trigger incidents on demand in the live
demo and to give tests a deterministic, label-rich signal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import POINTS_PER_DAY


def generate(
    n_points: int = 2880,  # ~10 days at 5-min cadence
    period: int = POINTS_PER_DAY,
    n_anomalies: int = 6,
    anomaly_magnitude: float = 6.0,
    noise: float = 1.0,
    freq: str = "5min",
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a seasonal time series with injected point/collective anomalies.

    Returns a frame with ``timestamp``, ``value`` and a boolean ``is_anomaly``.
    Deterministic for a given ``seed``.
    """
    if n_anomalies < 0:
        raise ValueError("n_anomalies must be >= 0")
    rng = np.random.default_rng(seed)

    t = np.arange(n_points)
    daily = 10.0 * np.sin(2 * np.pi * t / period)
    weekly = 3.0 * np.sin(2 * np.pi * t / (period * 7))
    trend = 0.001 * t
    baseline = 50.0 + daily + weekly + trend
    value = baseline + rng.normal(0.0, noise, size=n_points)

    is_anomaly = np.zeros(n_points, dtype=bool)
    # Keep injected anomalies away from the edges so rolling features have context.
    margin = period
    if n_anomalies > 0 and n_points > 2 * margin:
        idx = rng.choice(
            np.arange(margin, n_points - margin), size=n_anomalies, replace=False
        )
        for i in idx:
            width = int(rng.integers(1, 6))  # point or short collective anomaly
            sign = 1.0 if rng.random() > 0.5 else -1.0
            seg = slice(i, min(i + width, n_points))
            value[seg] += sign * anomaly_magnitude * noise * rng.uniform(2.0, 4.0)
            is_anomaly[seg] = True

    timestamps = pd.date_range("2024-01-01", periods=n_points, freq=freq)
    return pd.DataFrame(
        {"timestamp": timestamps, "value": value, "is_anomaly": is_anomaly}
    )
