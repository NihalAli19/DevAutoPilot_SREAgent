"""Phase 1 slice 1 tests: synthetic generator, NAB loader, feature engineering."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import CONFIG
from data.loader import load_nab_sample
from data.synthetic import generate
from features.engineering import (
    FEATURE_VERSION,
    build_features,
    feature_columns,
    split_xy,
)

# --------------------------------------------------------------------------- #
# Synthetic generator
# --------------------------------------------------------------------------- #


def test_synthetic_shape_and_columns():
    df = generate(n_points=1000, n_anomalies=5, seed=1)
    assert list(df.columns) == ["timestamp", "value", "is_anomaly"]
    assert len(df) == 1000
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert df["value"].notna().all()


def test_synthetic_is_reproducible():
    a = generate(n_points=500, seed=7)
    b = generate(n_points=500, seed=7)
    pd.testing.assert_frame_equal(a, b)
    c = generate(n_points=500, seed=8)
    assert not a["value"].equals(c["value"])


def test_synthetic_injects_anomalies():
    df = generate(n_points=2000, n_anomalies=6, seed=3)
    assert df["is_anomaly"].sum() >= 6  # at least one point per injected anomaly
    assert df["is_anomaly"].sum() < len(df)  # but not everything


# --------------------------------------------------------------------------- #
# NAB sample loader
# --------------------------------------------------------------------------- #


def test_load_nab_sample_is_labeled_and_clean():
    df = load_nab_sample()
    assert list(df.columns) == ["timestamp", "value", "is_anomaly"]
    assert len(df) > 200
    assert df["value"].notna().all()
    assert df["timestamp"].is_monotonic_increasing
    # The vendored slice was chosen to contain a real labeled anomaly window.
    assert df["is_anomaly"].any()
    assert (~df["is_anomaly"]).any()


# --------------------------------------------------------------------------- #
# Feature engineering
# --------------------------------------------------------------------------- #


def test_build_features_no_nan_and_expected_columns():
    feats = build_features(load_nab_sample())
    expected = feature_columns()
    assert set(expected).issubset(feats.columns)
    assert feats[expected].notna().all().all()  # no NaNs survive into the matrix
    assert len(feats) > 0
    assert "is_anomaly" in feats.columns  # label passed through


def test_features_drop_warmup_rows():
    raw = load_nab_sample()
    feats = build_features(raw)
    # The largest rolling window removes at least that many warmup rows.
    assert len(feats) <= len(raw) - max(CONFIG.rolling_windows) + 1


def test_split_xy_alignment_and_version():
    feats = build_features(load_nab_sample())
    x, y = split_xy(feats)
    assert y is not None
    assert len(x) == len(y) == len(feats)
    assert list(x.columns) == feature_columns()
    assert set(np.unique(y)).issubset({0, 1})
    assert FEATURE_VERSION == CONFIG.feature_version


def test_features_preserve_both_label_classes():
    feats = build_features(load_nab_sample())
    _, y = split_xy(feats)
    assert y is not None and y.sum() > 0 and (y == 0).sum() > 0
