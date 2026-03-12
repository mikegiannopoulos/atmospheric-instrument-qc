"""Lightweight tests for core pipeline behavior."""

from __future__ import annotations

import unittest

import pandas as pd

from atmospheric_instrument_qc.calibration import apply_signal_calibration
from atmospheric_instrument_qc.generate_demo_data import generate_demo_dataset
from atmospheric_instrument_qc.ingest import REQUIRED_COLUMNS, validate_required_columns
from atmospheric_instrument_qc.qc import FLAG_GOOD, FLAG_INVALID, FLAG_SUSPECT, apply_qc_flags


class TestDemoDataGeneration(unittest.TestCase):
    """Tests for demo-data generation utilities."""

    def test_generate_demo_dataset_shape_and_anomalies(self) -> None:
        df, anomalies = generate_demo_dataset()

        self.assertEqual(len(df), 504)
        self.assertEqual(
            list(df.columns),
            ["timestamp", "raw_signal", "temperature_c", "pressure_hpa", "relative_humidity"],
        )
        self.assertEqual(len(anomalies["raw_signal_spikes"]), 6)
        self.assertEqual(anomalies["drift_range_raw_signal"], [0.0, 12.0])
        self.assertEqual({k: len(v) for k, v in anomalies["missing_values"].items()}, {
            "raw_signal": 4,
            "temperature_c": 3,
            "pressure_hpa": 2,
            "relative_humidity": 3,
        })


class TestIngestValidation(unittest.TestCase):
    """Tests for ingestion validation behavior."""

    def test_validate_required_columns_raises_when_missing(self) -> None:
        df = pd.DataFrame({"timestamp": ["2025-01-01T00:00:00"], "raw_signal": [1.0]})

        with self.assertRaises(ValueError):
            validate_required_columns(df, REQUIRED_COLUMNS)


class TestCalibrationLogic(unittest.TestCase):
    """Tests for calibration calculations."""

    def test_calibration_applies_offset_scale_and_drift(self) -> None:
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2025-01-01T00:00:00", "2025-01-02T00:00:00"]),
                "raw_signal": [10.0, 10.0],
            }
        )
        config = {
            "offset": 2.0,
            "scale_factor": 2.0,
            "drift_correction": {"enabled": True, "rate_per_day": 1.0},
        }

        calibrated = apply_signal_calibration(df, config)

        self.assertEqual(calibrated["calibrated_signal"].iloc[0], 24.0)
        self.assertEqual(calibrated["calibrated_signal"].iloc[1], 23.0)


class TestQcRules(unittest.TestCase):
    """Tests for QC flagging conventions and rules."""

    def test_qc_flags_missing_range_and_spike(self) -> None:
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    [
                        "2025-01-01T00:00:00",
                        "2025-01-01T01:00:00",
                        "2025-01-01T02:00:00",
                        "2025-01-01T03:00:00",
                    ]
                ),
                "raw_signal": [10.0, 60.0, None, 20.0],
                "calibrated_signal": [10.0, 60.0, None, 1000.0],
            }
        )
        qc_config = {
            "min_physical_value": -50.0,
            "max_physical_value": 500.0,
            "spike_jump_threshold": 20.0,
            "trend_window_points": 3,
            "max_abs_trend_per_day": 1e6,
        }

        qc_df, _ = apply_qc_flags(df, qc_config)

        self.assertEqual(int(qc_df.loc[0, "qc_flag"]), FLAG_GOOD)
        self.assertEqual(int(qc_df.loc[1, "qc_flag"]), FLAG_SUSPECT)
        self.assertEqual(int(qc_df.loc[2, "qc_flag"]), FLAG_INVALID)
        self.assertEqual(int(qc_df.loc[3, "qc_flag"]), FLAG_INVALID)
        self.assertIn("sudden_jump", str(qc_df.loc[1, "qc_reason"]))
        self.assertIn("missing_value", str(qc_df.loc[2, "qc_reason"]))
        self.assertIn("out_of_physical_range", str(qc_df.loc[3, "qc_reason"]))


if __name__ == "__main__":
    unittest.main()
