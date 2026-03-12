"""Visualization utilities for atmospheric instrument QC outputs.

Plots generated here are intended for technical reporting and pipeline checks.
All plots are derived from simulated demo data produced in earlier stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .config import resolve_project_path

QC_COLORS = {
    0: "#2e7d32",  # good
    1: "#f9a825",  # suspect
    2: "#c62828",  # invalid
}


@dataclass(frozen=True)
class VisualizationReport:
    """Summary of generated figure outputs."""

    input_path: Path
    figure_paths: list[Path]


def _apply_plot_style() -> None:
    """Apply consistent, publication-oriented matplotlib style."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )


def load_qc_dataset(input_path: Path) -> pd.DataFrame:
    """Load processed QC dataset for plotting."""
    if not input_path.exists():
        raise FileNotFoundError(f"QC dataset not found: {input_path}")
    return pd.read_csv(input_path, parse_dates=["timestamp"])


def plot_raw_vs_calibrated(df: pd.DataFrame, output_path: Path) -> None:
    """Plot raw and calibrated time series on the same axes."""
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(df["timestamp"], df["raw_signal"], color="#6c757d", linewidth=1.0, alpha=0.75, label="Raw signal")
    ax.plot(
        df["timestamp"],
        df["calibrated_signal"],
        color="#1f77b4",
        linewidth=1.1,
        alpha=0.9,
        label="Calibrated signal",
    )
    ax.set_title("Raw vs Calibrated Signal Over Time (Demo Data)")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Signal")
    ax.legend(loc="upper right", frameon=True)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def plot_qc_flags_over_time(df: pd.DataFrame, output_path: Path) -> None:
    """Plot QC flags over time with color-coded categories."""
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(df["timestamp"], df["qc_flag"], color="#37474f", linewidth=0.9, drawstyle="steps-mid")
    for flag, color in QC_COLORS.items():
        mask = df["qc_flag"] == flag
        ax.scatter(
            df.loc[mask, "timestamp"],
            df.loc[mask, "qc_flag"],
            s=14,
            color=color,
            alpha=0.9,
            label=f"Flag {flag}",
        )
    ax.set_title("QC Flags Over Time")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("QC Flag")
    ax.set_yticks([0, 1, 2])
    ax.set_ylim(-0.2, 2.2)
    ax.legend(loc="upper right", frameon=True, ncol=3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def plot_calibrated_distribution(df: pd.DataFrame, output_path: Path) -> None:
    """Plot calibrated signal distribution with reference lines."""
    signal = df["calibrated_signal"].dropna()
    mean_value = signal.mean()
    median_value = signal.median()

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.hist(signal, bins=36, color="#4c78a8", edgecolor="white", linewidth=0.6, alpha=0.9)
    ax.axvline(mean_value, color="#d81b60", linestyle="--", linewidth=1.5, label=f"Mean: {mean_value:.2f}")
    ax.axvline(median_value, color="#00897b", linestyle="-.", linewidth=1.4, label=f"Median: {median_value:.2f}")
    ax.set_title("Distribution of Calibrated Signal")
    ax.set_xlabel("Calibrated signal")
    ax.set_ylabel("Count")
    ax.legend(loc="upper right", frameon=True)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def generate_qc_figures(config: dict[str, Any]) -> VisualizationReport:
    """Generate all required figures from processed QC output."""
    input_path = resolve_project_path(config["processed_data_path"]) / "demo_sensor_data_qc.csv"
    figures_dir = resolve_project_path(config["figures_path"])
    figures_dir.mkdir(parents=True, exist_ok=True)
    df = load_qc_dataset(input_path)

    _apply_plot_style()

    fig_paths = [
        figures_dir / "demo_raw_vs_calibrated_timeseries.png",
        figures_dir / "demo_qc_flags_over_time.png",
        figures_dir / "demo_calibrated_signal_distribution.png",
    ]

    plot_raw_vs_calibrated(df, fig_paths[0])
    plot_qc_flags_over_time(df, fig_paths[1])
    plot_calibrated_distribution(df, fig_paths[2])

    return VisualizationReport(input_path=input_path, figure_paths=fig_paths)
