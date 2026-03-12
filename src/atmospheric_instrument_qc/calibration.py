"""Calibration utilities for atmospheric instrument demo data.

This stage applies a simple, configurable calibration model to `raw_signal`
and writes an interim calibrated dataset. It preserves original raw columns so
later QA/QC steps can compare pre/post calibration behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import resolve_project_path

REQUIRED_COLUMNS = ("timestamp", "raw_signal")


@dataclass(frozen=True)
class CalibrationReport:
    """Summary metadata for the calibration stage."""

    input_path: Path
    output_path: Path
    row_count: int
    scale_factor: float
    offset: float
    drift_correction_enabled: bool
    drift_rate_per_day: float
    calibrated_non_null_count: int
    raw_mean: float
    calibrated_mean: float


def load_interim_dataset(input_path: Path) -> pd.DataFrame:
    """Load an interim dataset and parse timestamps."""
    if not input_path.exists():
        raise FileNotFoundError(f"Ingestion output not found: {input_path}")
    return pd.read_csv(input_path, parse_dates=["timestamp"])


def validate_calibration_inputs(df: pd.DataFrame) -> None:
    """Ensure required columns exist before calibration."""
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Calibration input missing required columns: {joined}")


def _elapsed_days_from_start(timestamps: pd.Series) -> pd.Series:
    """Compute elapsed days from the first valid timestamp."""
    first_timestamp = timestamps.iloc[0]
    return (timestamps - first_timestamp).dt.total_seconds() / 86400.0


def apply_signal_calibration(df: pd.DataFrame, calibration_config: dict[str, Any]) -> pd.DataFrame:
    """Apply offset/scale calibration plus optional linear drift correction."""
    calibrated = df.copy()
    raw = calibrated["raw_signal"]

    offset = float(calibration_config.get("offset", 0.0))
    scale_factor = float(calibration_config.get("scale_factor", 1.0))
    drift_config = calibration_config.get("drift_correction", {}) or {}
    drift_enabled = bool(drift_config.get("enabled", False))
    drift_rate_per_day = float(drift_config.get("rate_per_day", 0.0))

    calibrated_signal = (raw + offset) * scale_factor
    if drift_enabled:
        elapsed_days = _elapsed_days_from_start(calibrated["timestamp"])
        calibrated_signal = calibrated_signal - drift_rate_per_day * elapsed_days

    calibrated["calibrated_signal"] = calibrated_signal
    return calibrated


def save_calibrated_dataset(df: pd.DataFrame, output_path: Path) -> None:
    """Write calibrated dataset to interim storage."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, date_format="%Y-%m-%dT%H:%M:%S")


def calibrate_demo_sensor_data(config: dict[str, Any]) -> CalibrationReport:
    """Run calibration for the demo ingestion output and save calibrated data."""
    input_path = resolve_project_path(config["interim_data_path"]) / "demo_sensor_data_loaded.csv"
    output_path = resolve_project_path(config["interim_data_path"]) / "demo_sensor_data_calibrated.csv"

    calibration_config = config.get("calibration_defaults", {})
    scale_factor = float(calibration_config.get("scale_factor", 1.0))
    offset = float(calibration_config.get("offset", 0.0))
    drift_config = calibration_config.get("drift_correction", {}) or {}
    drift_enabled = bool(drift_config.get("enabled", False))
    drift_rate_per_day = float(drift_config.get("rate_per_day", 0.0))

    df = load_interim_dataset(input_path)
    validate_calibration_inputs(df)
    calibrated = apply_signal_calibration(df, calibration_config)
    save_calibrated_dataset(calibrated, output_path)

    raw_non_null = calibrated["raw_signal"].dropna()
    calibrated_non_null = calibrated["calibrated_signal"].dropna()
    raw_mean = float(raw_non_null.mean()) if not raw_non_null.empty else float(np.nan)
    calibrated_mean = (
        float(calibrated_non_null.mean()) if not calibrated_non_null.empty else float(np.nan)
    )

    return CalibrationReport(
        input_path=input_path,
        output_path=output_path,
        row_count=len(calibrated),
        scale_factor=scale_factor,
        offset=offset,
        drift_correction_enabled=drift_enabled,
        drift_rate_per_day=drift_rate_per_day,
        calibrated_non_null_count=int(calibrated_non_null.count()),
        raw_mean=raw_mean,
        calibrated_mean=calibrated_mean,
    )
