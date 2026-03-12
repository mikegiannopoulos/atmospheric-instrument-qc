"""Generate simulated atmospheric demo data for development and testing.

This module intentionally creates synthetic data and injects controlled
anomalies (missing values and outliers). The output is for demonstration and
pipeline development only, not real instrument observations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import load_config, resolve_project_path


def _sample_unique_indices(
    rng: np.random.Generator, total: int, count: int, blocked: set[int]
) -> list[int]:
    """Sample unique row indices while avoiding already selected indices."""
    available = np.array(sorted(set(range(total)) - blocked))
    if count > len(available):
        raise ValueError("Not enough available indices to sample unique anomalies.")

    selected = rng.choice(available, size=count, replace=False)
    selected_list = sorted(int(idx) for idx in selected)
    blocked.update(selected_list)
    return selected_list


def generate_demo_dataset(
    start: str = "2025-01-01 00:00:00",
    periods: int = 24 * 21,
    freq: str = "1h",
    seed: int = 42,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Create a synthetic atmospheric time series with realistic variability."""
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range(start=start, periods=periods, freq=freq)
    n_rows = len(timestamps)

    hours = np.arange(n_rows, dtype=float)
    daily_phase = 2.0 * np.pi * (hours % 24) / 24.0
    synoptic_phase = 2.0 * np.pi * hours / (24.0 * 5.0)
    weekly_phase = 2.0 * np.pi * hours / (24.0 * 7.0)

    temperature_c = (
        13.0
        + 7.0 * np.sin(daily_phase - np.pi / 2.0)
        + 1.8 * np.sin(weekly_phase)
        + rng.normal(0.0, 0.9, n_rows)
    )
    pressure_hpa = (
        1013.0
        + 5.5 * np.sin(synoptic_phase)
        + 1.2 * np.sin(weekly_phase + 0.8)
        + rng.normal(0.0, 0.7, n_rows)
    )
    relative_humidity = (
        67.0
        - 17.0 * np.sin(daily_phase - np.pi / 2.0)
        + 4.0 * np.sin(weekly_phase + 1.2)
        + rng.normal(0.0, 3.5, n_rows)
    )
    relative_humidity = np.clip(relative_humidity, 20.0, 100.0)

    # Slight positive drift mimics slowly changing instrument response over time.
    drift = np.linspace(0.0, 12.0, n_rows)
    raw_signal = (
        175.0
        + 0.95 * relative_humidity
        - 1.1 * temperature_c
        + 0.04 * (pressure_hpa - 1013.0)
        + drift
        + rng.normal(0.0, 2.2, n_rows)
    )

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "raw_signal": raw_signal,
            "temperature_c": temperature_c,
            "pressure_hpa": pressure_hpa,
            "relative_humidity": relative_humidity,
        }
    )

    blocked_indices: set[int] = set()
    raw_spike_idx = _sample_unique_indices(rng, n_rows, 6, blocked_indices)
    temp_outlier_idx = _sample_unique_indices(rng, n_rows, 2, blocked_indices)
    pressure_outlier_idx = _sample_unique_indices(rng, n_rows, 2, blocked_indices)
    humidity_outlier_idx = _sample_unique_indices(rng, n_rows, 2, blocked_indices)

    df.loc[raw_spike_idx, "raw_signal"] += rng.choice(
        [55.0, 70.0, 85.0, -60.0, -75.0], size=len(raw_spike_idx), replace=True
    )
    df.loc[temp_outlier_idx, "temperature_c"] += rng.choice(
        [9.0, -11.0], size=len(temp_outlier_idx), replace=True
    )
    df.loc[pressure_outlier_idx, "pressure_hpa"] += rng.choice(
        [15.0, -18.0], size=len(pressure_outlier_idx), replace=True
    )
    df.loc[humidity_outlier_idx[0], "relative_humidity"] = 8.0
    df.loc[humidity_outlier_idx[1], "relative_humidity"] = 103.0

    missing_counts = {
        "raw_signal": 4,
        "temperature_c": 3,
        "pressure_hpa": 2,
        "relative_humidity": 3,
    }
    missing_indices: dict[str, list[int]] = {}
    for column, count in missing_counts.items():
        idx = _sample_unique_indices(rng, n_rows, count, blocked_indices)
        df.loc[idx, column] = np.nan
        missing_indices[column] = idx

    anomalies: dict[str, Any] = {
        "raw_signal_spikes": raw_spike_idx,
        "temperature_outliers": temp_outlier_idx,
        "pressure_outliers": pressure_outlier_idx,
        "humidity_outliers": humidity_outlier_idx,
        "missing_values": missing_indices,
        "drift_range_raw_signal": [float(drift.min()), float(drift.max())],
    }
    return df, anomalies


def save_demo_dataset(output_path: Path | None = None) -> tuple[Path, pd.DataFrame, dict[str, Any]]:
    """Generate and save the simulated demo dataset to CSV."""
    config = load_config()
    raw_data_dir = resolve_project_path(config["raw_data_path"])
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    target = output_path if output_path else raw_data_dir / "demo_sensor_data.csv"
    df, anomalies = generate_demo_dataset()
    df.to_csv(target, index=False, date_format="%Y-%m-%dT%H:%M:%S")
    return target, df, anomalies


def main() -> None:
    """Create and persist synthetic demo data for local development."""
    output_path, df, anomalies = save_demo_dataset()
    print(f"Simulated demo dataset written to: {output_path}")
    print(
        f"Rows: {len(df)} | Start: {df['timestamp'].iloc[0]} | "
        f"End: {df['timestamp'].iloc[-1]}"
    )
    print(f"Injected raw_signal spikes: {len(anomalies['raw_signal_spikes'])}")
    print(
        "Injected missing values: "
        f"{ {k: len(v) for k, v in anomalies['missing_values'].items()} }"
    )
    drift_min, drift_max = anomalies["drift_range_raw_signal"]
    print(f"Injected calibration drift in raw_signal: {drift_min:.1f} to {drift_max:.1f}")


if __name__ == "__main__":
    main()
