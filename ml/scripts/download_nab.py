"""Download full NAB series + labels into the gitignored raw dir.

Only a small slice is vendored in the repo (for tests/CI); full training data is
fetched on demand with this script. Stdlib-only (urllib) so it needs no extra deps.

Usage:
    python -m scripts.download_nab            # default series set
    python -m scripts.download_nab a/b.csv    # specific "<category>/<file>" keys
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

# scripts/ is not a package on sys.path the same way; make config importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import RAW_DIR  # noqa: E402

NAB_RAW_BASE = "https://raw.githubusercontent.com/numenta/NAB/master"
LABELS_PATH = "labels/combined_windows.json"

DEFAULT_SERIES = [
    "realAWSCloudwatch/ec2_cpu_utilization_5f5533.csv",
    "realAWSCloudwatch/ec2_network_in_5abac7.csv",
    "realKnownCause/nyc_taxi.csv",
]


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"GET {url}")
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (trusted host)
        dest.write_bytes(resp.read())
    print(f"  -> {dest} ({dest.stat().st_size} bytes)")


def download(series: list[str]) -> None:
    """Download the given NAB series (by key) and the shared labels file."""
    _download(f"{NAB_RAW_BASE}/{LABELS_PATH}", RAW_DIR / "combined_windows.json")
    for key in series:
        _download(f"{NAB_RAW_BASE}/data/{key}", RAW_DIR / Path(key).name)


def main() -> None:
    series = sys.argv[1:] or DEFAULT_SERIES
    download(series)
    print(f"Done. Raw data in {RAW_DIR}")


if __name__ == "__main__":
    main()
