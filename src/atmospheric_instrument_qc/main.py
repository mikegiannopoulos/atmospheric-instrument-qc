"""Command-line entry point for the atmospheric instrument QC demo pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .calibration import calibrate_demo_sensor_data
from .config import get_project_root, load_config, resolve_project_path
from .generate_demo_data import save_demo_dataset
from .ingest import ingest_demo_sensor_data
from .qc import run_demo_qc
from .visualization import generate_qc_figures

COMMANDS = (
    "generate-demo-data",
    "ingest",
    "calibrate",
    "qc",
    "plot",
    "run-all",
)

DIRECTORY_KEYS = (
    "raw_data_path",
    "interim_data_path",
    "processed_data_path",
    "figures_path",
)


def verify_required_directories(config: dict[str, Any], project_root: Path) -> list[Path]:
    """Return any required project directories that are missing."""
    missing: list[Path] = []
    for key in DIRECTORY_KEYS:
        directory = resolve_project_path(str(config[key]), project_root)
        if not directory.is_dir():
            missing.append(directory)
    return missing


def _build_parser() -> argparse.ArgumentParser:
    """Build command-line parser for pipeline stage execution."""
    parser = argparse.ArgumentParser(
        prog="python -m atmospheric_instrument_qc.main",
        description="Run atmospheric instrument QC demo pipeline stages.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional path to a YAML config file (default: config/config.yaml).",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = False
    for command in COMMANDS:
        subparsers.add_parser(command, help=f"Run: {command}")
    parser.set_defaults(command="run-all")
    return parser


def _print_header(config: dict[str, Any], project_root: Path) -> None:
    """Print a concise startup header for CLI runs."""
    print(f"[{config['project_name']}] configuration loaded successfully.")
    print(f"Project root: {project_root}")


def _ensure_required_directories(config: dict[str, Any], project_root: Path) -> None:
    """Create required top-level project directories if missing."""
    missing_dirs = verify_required_directories(config, project_root)
    if not missing_dirs:
        print("All required directories are present.")
        return

    print("Missing required directories detected; creating them:")
    for path in missing_dirs:
        path.mkdir(parents=True, exist_ok=True)
        print(f" - created: {path}")


def _run_generate_demo_data(config: dict[str, Any]) -> None:
    """Run demo data generation stage."""
    output_file = resolve_project_path(config["raw_data_path"]) / "demo_sensor_data.csv"
    output_path, df, anomalies = save_demo_dataset(output_path=output_file)
    print("\nDemo data generation stage complete.")
    print(f"Output file: {output_path}")
    print(f"Rows generated: {len(df)}")
    print(
        "Anomalies injected: "
        f"spikes={len(anomalies['raw_signal_spikes'])}, "
        f"missing={ {k: len(v) for k, v in anomalies['missing_values'].items()} }, "
        f"drift_range={anomalies['drift_range_raw_signal']}"
    )


def _run_ingest(config: dict[str, Any]) -> None:
    """Run ingestion stage and print summary."""
    report = ingest_demo_sensor_data(config)
    print("\nIngestion stage complete.")
    print(f"Input file: {report.input_path}")
    print(f"Interim output: {report.output_path}")
    print(
        f"Rows loaded: {report.row_count} | "
        f"Start: {report.start_timestamp} | End: {report.end_timestamp}"
    )
    print(f"Median time step: {report.median_time_step_minutes:.1f} minutes")
    print(f"Validation passed: {'yes' if report.validation_passed else 'no'}")
    print("Missing values by required column:")
    for column, count in report.missing_value_counts.items():
        print(f" - {column}: {count}")


def _run_calibrate(config: dict[str, Any]) -> None:
    """Run calibration stage and print summary."""
    calibration_report = calibrate_demo_sensor_data(config)
    print("\nCalibration stage complete.")
    print(f"Input file: {calibration_report.input_path}")
    print(f"Interim output: {calibration_report.output_path}")
    print(
        "Calibration parameters: "
        f"offset={calibration_report.offset:.3f}, "
        f"scale_factor={calibration_report.scale_factor:.3f}, "
        "drift_correction="
        f"{'enabled' if calibration_report.drift_correction_enabled else 'disabled'}"
        + (
            f" ({calibration_report.drift_rate_per_day:.3f} units/day)"
            if calibration_report.drift_correction_enabled
            else ""
        )
    )
    print(f"Rows calibrated: {calibration_report.calibrated_non_null_count}")
    print(
        "Signal mean (non-null): "
        f"raw={calibration_report.raw_mean:.3f}, "
        f"calibrated={calibration_report.calibrated_mean:.3f}"
    )


def _run_qc(config: dict[str, Any]) -> None:
    """Run QC stage and print summary."""
    qc_report = run_demo_qc(config)
    print("\nQC stage complete.")
    print(f"Input file: {qc_report.input_path}")
    print(f"Processed output: {qc_report.output_path}")
    print(f"Rows evaluated: {qc_report.row_count}")
    print("QC counts by flag (0=good, 1=suspect, 2=invalid):")
    for flag, count in sorted(qc_report.flag_counts.items()):
        print(f" - {flag}: {count}")
    print("QC triggers by rule:")
    for rule, count in qc_report.rule_counts.items():
        print(f" - {rule}: {count}")


def _run_plot(config: dict[str, Any]) -> None:
    """Run visualization stage and print generated files."""
    viz_report = generate_qc_figures(config)
    print("\nVisualization stage complete.")
    print(f"Input file: {viz_report.input_path}")
    print("Generated figure files:")
    for figure_path in viz_report.figure_paths:
        print(f" - {figure_path}")


def _run_command(command: str, config: dict[str, Any]) -> None:
    """Dispatch and execute one pipeline command."""
    if command == "generate-demo-data":
        _run_generate_demo_data(config)
        return
    if command == "ingest":
        _run_ingest(config)
        return
    if command == "calibrate":
        _run_calibrate(config)
        return
    if command == "qc":
        _run_qc(config)
        return
    if command == "plot":
        _run_plot(config)
        return
    if command == "run-all":
        _run_generate_demo_data(config)
        _run_ingest(config)
        _run_calibrate(config)
        _run_qc(config)
        _run_plot(config)
        return
    raise ValueError(f"Unsupported command: {command}")


def main(argv: list[str] | None = None) -> int:
    """Run selected pipeline stage(s) from CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config)
    project_root = get_project_root()
    _print_header(config, project_root)
    _ensure_required_directories(config, project_root)

    try:
        _run_command(args.command, config)
    except FileNotFoundError as exc:
        print(f"\nError: {exc}")
        print("Run prerequisite steps first, or use: python -m atmospheric_instrument_qc.main run-all")
        return 1
    except (ValueError, KeyError) as exc:
        print(f"\nError: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
