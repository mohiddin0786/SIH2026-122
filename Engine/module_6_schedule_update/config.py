"""
module_6_schedule_update/config.py — Configuration for Schedule Update Engine.

Externalized, tunable configuration. Nothing here is a business-logic decision
by itself; it is the set of knobs the module reads from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ScheduleUpdateConfig:
    """Configuration for the Schedule Update Engine.

    Attributes:
        schedule_master_path: Path to the baseline Schedule Master CSV.
        execution_state_path: Path to the execution state persistence file (CSV).
        auto_create_execution_store: Whether to create the execution store
            automatically if it doesn't exist.
        allow_state_regression: If False (default), prevent COMPLETED activities
            from reverting to IN_PROGRESS due to older reports.
        timestamp_format: ISO-8601 format for timestamps.
    """

    schedule_master_path: str = "Data/schedule_master_v1.csv"
    execution_state_path: str = "Data/execution_state.csv"
    auto_create_execution_store: bool = True
    allow_state_regression: bool = False
    timestamp_format: str = "%Y-%m-%dT%H:%M:%SZ"

    def __post_init__(self) -> None:
        # Convert to absolute paths if relative
        self.schedule_master_path = str(Path(self.schedule_master_path).resolve())
        self.execution_state_path = str(Path(self.execution_state_path).resolve())


# Default configuration instance
DEFAULT_CONFIG = ScheduleUpdateConfig()


def load_config_from_dict(data: dict) -> ScheduleUpdateConfig:
    """Build a ScheduleUpdateConfig from a plain dict (e.g., loaded from JSON/YAML)."""
    return ScheduleUpdateConfig(**{k: v for k, v in data.items() if k in ScheduleUpdateConfig.__dataclass_fields__})