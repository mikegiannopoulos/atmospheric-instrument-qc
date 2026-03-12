"""Load and summarize a small real atmospheric CO2 example dataset.

Dataset source:
NOAA Global Monitoring Laboratory (GML), Mauna Loa (MLO) in-situ hourly CO2.
This module reads a local demonstration sample prepared from the public source.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import get_project_root

REQUIRED_COLUMNS = ("timestamp", "co2_ppm")


def get_default_real_example_path() -> Path:
    """Return the default local path to the real-data example sample."""
    return get_project_root() / "data" / "example_real" / "co2_sample.csv"


def load_real_example_dataset(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Load the real example dataset and validate required columns."""
    path = Path(csv_path) if csv_path else get_default_real_example_path()
    if not path.exists():
        raise FileNotFoundError(f"Real example dataset not found: {path}")

    df = pd.read_csv(path, parse_dates=["timestamp"])
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required columns in real example dataset: {joined}")

    return df


def summarize_real_example(df: pd.DataFrame) -> dict[str, float | int | str]:
    """Compute basic descriptive statistics for the real example data."""
    co2 = pd.to_numeric(df["co2_ppm"], errors="coerce")
    summary: dict[str, float | int | str] = {
        "rows": int(len(df)),
        "missing_co2_ppm": int(co2.isna().sum()),
        "start_timestamp": str(df["timestamp"].min()),
        "end_timestamp": str(df["timestamp"].max()),
        "mean_co2_ppm": float(co2.mean()),
        "std_co2_ppm": float(co2.std()),
        "min_co2_ppm": float(co2.min()),
        "max_co2_ppm": float(co2.max()),
    }
    return summary


def main() -> None:
    """Load and print summary statistics for the real-data sample."""
    path = get_default_real_example_path()
    df = load_real_example_dataset(path)
    summary = summarize_real_example(df)

    print("Real Data Example: NOAA GML Mauna Loa hourly CO2 sample")
    print(f"Input file: {path}")
    print(f"Rows: {summary['rows']}")
    print(f"Time range: {summary['start_timestamp']} to {summary['end_timestamp']}")
    print(f"Missing co2_ppm: {summary['missing_co2_ppm']}")
    print(
        "CO2 ppm statistics: "
        f"mean={summary['mean_co2_ppm']:.3f}, "
        f"std={summary['std_co2_ppm']:.3f}, "
        f"min={summary['min_co2_ppm']:.3f}, "
        f"max={summary['max_co2_ppm']:.3f}"
    )


if __name__ == "__main__":
    main()
