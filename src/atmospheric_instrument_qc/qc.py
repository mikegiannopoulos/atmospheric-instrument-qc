"""Quality-control checks and flagging for calibrated atmospheric data.

This module applies transparent rule-based checks:
- missing value checks
- physical range checks
- spike detection from sudden jumps
- trend-based suspect flagging from rolling linear slopes
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import resolve_project_path

FLAG_GOOD = 0
FLAG_SUSPECT = 1
FLAG_INVALID = 2

REQUIRED_COLUMNS = ("timestamp", "raw_signal", "calibrated_signal")


@dataclass(frozen=True)
class QcReport:
    """Summary metadata produced by the QC stage."""

    input_path: Path
    output_path: Path
    row_count: int
    flag_counts: dict[int, int]
    rule_counts: dict[str, int]


def load_calibrated_dataset(input_path: Path) -> pd.DataFrame:
    """Load calibrated dataset and parse timestamps."""
    if not input_path.exists():
        raise FileNotFoundError(f"Calibrated input file not found: {input_path}")
    return pd.read_csv(input_path, parse_dates=["timestamp"])


def validate_qc_columns(df: pd.DataFrame) -> None:
    """Ensure required columns are present before QC checks."""
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"QC input missing required columns: {joined}")


def _append_reason(reasons: pd.Series, mask: pd.Series, reason: str) -> pd.Series:
    """Append a QC reason label to rows where mask is true."""
    active = mask.fillna(False)
    empty_mask = active & reasons.eq("")
    non_empty_mask = active & ~reasons.eq("")
    reasons.loc[empty_mask] = reason
    reasons.loc[non_empty_mask] = reasons.loc[non_empty_mask] + ";" + reason
    return reasons


def detect_spikes(calibrated_signal: pd.Series, jump_threshold: float) -> pd.Series:
    """Flag sudden point-to-point jumps above threshold."""
    jump = calibrated_signal.diff().abs()
    return jump > jump_threshold


def detect_suspect_trend(
    timestamps: pd.Series, calibrated_signal: pd.Series, window_points: int, max_abs_slope_per_day: float
) -> tuple[pd.Series, pd.Series]:
    """Flag rows where smoothed trend slope exceeds threshold."""
    if window_points < 3:
        raise ValueError("trend_window_points must be at least 3.")

    # Smooth short-term variability first, then inspect slope of the smoothed baseline.
    smoothed = calibrated_signal.rolling(
        window=window_points, min_periods=max(3, window_points // 2)
    ).median()
    delta_days = timestamps.diff().dt.total_seconds() / 86400.0
    delta_days = delta_days.replace(0.0, np.nan)
    rolling_slope = smoothed.diff() / delta_days
    trend_mask = rolling_slope.abs() > max_abs_slope_per_day
    return trend_mask, rolling_slope


def apply_qc_flags(df: pd.DataFrame, qc_config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply QC rules and return flagged data with per-rule counts."""
    min_value = float(qc_config.get("min_physical_value", -np.inf))
    max_value = float(qc_config.get("max_physical_value", np.inf))
    spike_jump_threshold = float(qc_config.get("spike_jump_threshold", 35.0))
    trend_window_points = int(qc_config.get("trend_window_points", 72))
    max_abs_trend_per_day = float(qc_config.get("max_abs_trend_per_day", 3.0))

    qc_df = df.copy()
    reasons = pd.Series("", index=qc_df.index, dtype="object")
    flags = pd.Series(FLAG_GOOD, index=qc_df.index, dtype=int)

    missing_mask = qc_df[list(REQUIRED_COLUMNS)].isna().any(axis=1)
    range_mask = (qc_df["calibrated_signal"] < min_value) | (qc_df["calibrated_signal"] > max_value)
    spike_mask = detect_spikes(qc_df["calibrated_signal"], spike_jump_threshold)
    trend_mask, rolling_slope = detect_suspect_trend(
        qc_df["timestamp"],
        qc_df["calibrated_signal"],
        window_points=trend_window_points,
        max_abs_slope_per_day=max_abs_trend_per_day,
    )

    invalid_mask = missing_mask | range_mask
    suspect_mask = spike_mask | trend_mask

    flags.loc[invalid_mask] = FLAG_INVALID
    flags.loc[suspect_mask & ~invalid_mask] = FLAG_SUSPECT

    reasons = _append_reason(reasons, missing_mask, "missing_value")
    reasons = _append_reason(reasons, range_mask, "out_of_physical_range")
    reasons = _append_reason(reasons, spike_mask, "sudden_jump")
    reasons = _append_reason(reasons, trend_mask, "suspect_trend")
    reasons.loc[reasons.eq("")] = "good"

    qc_df["qc_flag"] = flags
    qc_df["qc_reason"] = reasons
    qc_df["qc_trend_slope_per_day"] = rolling_slope

    rule_counts = {
        "missing_value": int(missing_mask.sum()),
        "out_of_physical_range": int(range_mask.sum()),
        "sudden_jump": int(spike_mask.fillna(False).sum()),
        "suspect_trend": int(trend_mask.fillna(False).sum()),
    }
    return qc_df, rule_counts


def save_qc_results(df: pd.DataFrame, output_path: Path) -> None:
    """Write QC output to the processed data directory."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, date_format="%Y-%m-%dT%H:%M:%S")


def run_demo_qc(config: dict[str, Any]) -> QcReport:
    """Run QC checks for calibrated demo data and save processed output."""
    input_path = resolve_project_path(config["interim_data_path"]) / "demo_sensor_data_calibrated.csv"
    output_path = resolve_project_path(config["processed_data_path"]) / "demo_sensor_data_qc.csv"
    qc_config = config.get("qc_thresholds", {})

    df = load_calibrated_dataset(input_path)
    validate_qc_columns(df)
    qc_df, rule_counts = apply_qc_flags(df, qc_config)
    save_qc_results(qc_df, output_path)

    counts = qc_df["qc_flag"].value_counts().sort_index()
    flag_counts = {int(flag): int(count) for flag, count in counts.items()}

    return QcReport(
        input_path=input_path,
        output_path=output_path,
        row_count=len(qc_df),
        flag_counts=flag_counts,
        rule_counts=rule_counts,
    )
