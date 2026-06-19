# Vendored NAB sample (for tests/CI only)

This directory holds a **small slice** of the Numenta Anomaly Benchmark (NAB),
committed so tests and CI run without a network download. The full datasets are
fetched on demand via `ml/scripts/download_nab.py` into `ml/data/raw/` (gitignored).

## Contents
- `ec2_cpu_utilization_5f5533.csv` — a 681-row slice of NAB's
  `realAWSCloudwatch/ec2_cpu_utilization_5f5533.csv`, chosen to include a real
  labeled anomaly window (2014-02-18 → 2014-02-19).
- `combined_windows.json` — the NAB anomaly-window labels for that series.

## Source & license
- Source: https://github.com/numenta/NAB (`data/` and `labels/combined_windows.json`)
- NAB is licensed **AGPL-3.0**. This slice is included for benchmarking/testing and
  is attributed here. If AGPL is undesirable for this repo, replace the fixture with
  the synthetic generator (`ml/data/synthetic.py`) — the tests are written to work
  with either source — and download NAB locally instead of committing it.
