"""Configuration utilities for the atmospheric instrument QC project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_CONFIG_KEYS = {
    "project_name",
    "raw_data_path",
    "interim_data_path",
    "processed_data_path",
    "figures_path",
    "calibration_defaults",
    "qc_thresholds",
}


def get_project_root() -> Path:
    """Return the repository root based on the package location."""
    return Path(__file__).resolve().parents[2]


def get_default_config_path() -> Path:
    """Return the default path to the project YAML configuration file."""
    return get_project_root() / "config" / "config.yaml"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate YAML configuration from disk."""
    path = Path(config_path) if config_path else get_default_config_path()
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    if not isinstance(config, dict):
        raise ValueError(f"Configuration file must contain a top-level mapping: {path}")

    missing_keys = sorted(REQUIRED_CONFIG_KEYS - set(config))
    if missing_keys:
        joined = ", ".join(missing_keys)
        raise KeyError(f"Missing required configuration keys: {joined}")

    return config


def resolve_project_path(path_value: str | Path, project_root: str | Path | None = None) -> Path:
    """Resolve a project-relative path into an absolute path."""
    root = Path(project_root) if project_root else get_project_root()
    return (root / Path(path_value)).resolve()
