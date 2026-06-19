# Vendored NAB sample (for tests/CI only)

This directory holds a **small slice** of the Numenta Anomaly Benchmark (NAB),
committed so tests and CI run without a network download. The full datasets are
fetched on demand via `ml/scripts/download_nab.py` into `ml/data/raw/` (gitignored);
real training/metrics use the full local data, not this slice.

## Contents
- `ec2_cpu_utilization_5f5533.csv` — a 681-row slice of NAB's
  `realAWSCloudwatch/ec2_cpu_utilization_5f5533.csv`, chosen to include a real
  labeled anomaly window (2014-02-18 → 2014-02-19).
- `combined_windows.json` — the NAB anomaly-window labels for that series.

## Source
- Repository: <https://github.com/numenta/NAB>
- Series file: `data/realAWSCloudwatch/ec2_cpu_utilization_5f5533.csv`
- Labels file: `labels/combined_windows.json`

## License

NAB is distributed by Numenta under the **MIT License** (verified against
<https://github.com/numenta/NAB/blob/master/LICENSE.txt>; Numenta relicensed NAB
from AGPL-3.0 to MIT in 2024). The MIT license permits redistribution of this
slice in this repository. Full text reproduced below as required by the license:

```
Copyright 2014-2024 Numenta Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

> Alternative: the synthetic generator (`ml/data/synthetic.py`) produces a
> dependency-free, fully-controlled signal. The tests work with either source, so
> the fixture can be swapped if a self-contained dataset is ever preferred.
