"""Data ingestion utilities for simulated atmospheric sensor time series.

This module ingests raw CSV data, performs basic structural validation, and
writes a cleaned interim file. It intentionally avoids calibration and QA/QC
flagging, which are handled in later pipeline stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .config import resolve_project_path

REQUIRED_COLUMNS = (
    "timestamp",
    "raw_signal",
    "temperature_c",
    "pressure_hpa",
    "relative_humidity",
)


@dataclass(frozen=True)
class IngestionReport:
    """Summary metadata emitted after ingestion and basic validation."""

    input_path: Path
    output_path: Path
    row_count: int
    start_timestamp: pd.Timestamp
    end_timestamp: pd.Timestamp
    median_time_step_minutes: float
    validation_passed: bool
    missing_value_counts: dict[str, int]


def load_sensor_csv(csv_path: Path) -> pd.DataFrame:
    """Load raw sensor data from CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Raw data file not found: {csv_path}")
    return pd.read_csv(csv_path)


def validate_required_columns(df: pd.DataFrame, required_columns: tuple[str, ...]) -> None:
    """Raise if required columns are missing."""
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required columns: {joined}")


def parse_timestamps(df: pd.DataFrame, timestamp_column: str = "timestamp") -> pd.DataFrame:
    """Parse timestamp column and reject invalid entries."""
    parsed = df.copy()
    parsed[timestamp_column] = pd.to_datetime(parsed[timestamp_column], errors="coerce", utc=False)
    invalid_count = int(parsed[timestamp_column].isna().sum())
    if invalid_count > 0:
        raise ValueError(f"Found {invalid_count} invalid timestamp value(s) in '{timestamp_column}'.")
    return parsed


def sort_by_timestamp(df: pd.DataFrame, timestamp_column: str = "timestamp") -> pd.DataFrame:
    """Sort records chronologically."""
    return df.sort_values(timestamp_column).reset_index(drop=True)


def report_missing_values(df: pd.DataFrame, columns: tuple[str, ...]) -> dict[str, int]:
    """Return missing value counts for selected columns."""
    return {column: int(df[column].isna().sum()) for column in columns}


def save_interim_dataset(df: pd.DataFrame, output_path: Path) -> None:
    """Persist cleaned ingestion output to the interim directory."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, date_format="%Y-%m-%dT%H:%M:%S")


def ingest_demo_sensor_data(config: dict[str, Any]) -> IngestionReport:
    """Ingest the demo raw dataset and save a cleaned interim version."""
    raw_path = resolve_project_path(config["raw_data_path"]) / "demo_sensor_data.csv"
    interim_path = resolve_project_path(config["interim_data_path"]) / "demo_sensor_data_loaded.csv"

    df = load_sensor_csv(raw_path)
    validate_required_columns(df, REQUIRED_COLUMNS)
    df = parse_timestamps(df)
    df = sort_by_timestamp(df)

    missing_counts = report_missing_values(df, REQUIRED_COLUMNS)
    save_interim_dataset(df, interim_path)

    time_step = df["timestamp"].diff().dropna()
    median_step_minutes = (
        float(time_step.dt.total_seconds().median() / 60.0) if not time_step.empty else 0.0
    )

    return IngestionReport(
        input_path=raw_path,
        output_path=interim_path,
        row_count=len(df),
        start_timestamp=df["timestamp"].iloc[0],
        end_timestamp=df["timestamp"].iloc[-1],
        median_time_step_minutes=median_step_minutes,
        validation_passed=True,
        missing_value_counts=missing_counts,
    )
