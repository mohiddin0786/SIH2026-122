"""
module_6_schedule_update/repository.py — Execution State Persistence Layer.

Isolates persistence logic from business logic. Uses a simple CSV store
suitable for the SIH prototype. Does NOT modify the baseline Schedule Master.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from shared.exceptions import ScheduleUpdateError
from shared.schemas import ExecutionState
from .config import ScheduleUpdateConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)

# CSV column order for execution state store
EXECUTION_STATE_COLUMNS = [
    "activity_id",
    "actual_status",
    "actual_progress",
    "last_report_id",
    "last_update_timestamp",
]


@dataclass
class ExecutionStateRecord:
    """Internal representation of a stored execution state row."""
    activity_id: str
    actual_status: str
    actual_progress: Optional[float]
    last_report_id: Optional[str]
    last_update_timestamp: Optional[str]

    def to_execution_state(self) -> ExecutionState:
        """Convert to shared ExecutionState schema."""
        return ExecutionState(
            activity_id=self.activity_id,
            actual_status=self.actual_status,  # type: ignore[arg-type]
            actual_progress=self.actual_progress,
            last_report_id=self.last_report_id,
            last_update_timestamp=self.last_update_timestamp,
        )

    @classmethod
    def from_execution_state(cls, state: ExecutionState) -> "ExecutionStateRecord":
        """Create from shared ExecutionState schema."""
        return cls(
            activity_id=state.activity_id,
            actual_status=state.actual_status.value if state.actual_status else "UNKNOWN",
            actual_progress=state.actual_progress,
            last_report_id=state.last_report_id,
            last_update_timestamp=state.last_update_timestamp,
        )

    def to_dict(self) -> dict:
        """Convert to dict for CSV writing."""
        return {
            "activity_id": self.activity_id,
            "actual_status": self.actual_status,
            "actual_progress": self.actual_progress if self.actual_progress is not None else "",
            "last_report_id": self.last_report_id if self.last_report_id else "",
            "last_update_timestamp": self.last_update_timestamp if self.last_update_timestamp else "",
        }


class ExecutionStateRepository:
    """Repository for reading/writing execution state.

    Uses a CSV file for simple, transparent persistence. Thread-safe for
    single-writer scenarios (sufficient for this prototype).
    """

    def __init__(self, config: Optional[ScheduleUpdateConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._cache: Dict[str, ExecutionStateRecord] = {}
        self._loaded = False

    def _ensure_store_exists(self) -> None:
        """Create the execution state CSV with headers if it doesn't exist."""
        path = Path(self.config.execution_state_path)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=EXECUTION_STATE_COLUMNS)
                writer.writeheader()
            logger.info("Created execution state store at %s", path)

    def _load_all(self) -> None:
        """Load all records into memory cache."""
        if self._loaded:
            return

        self._ensure_store_exists()
        path = Path(self.config.execution_state_path)

        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame(columns=EXECUTION_STATE_COLUMNS)

        self._cache = {}
        for _, row in df.iterrows():
            record = ExecutionStateRecord(
                activity_id=row.get("activity_id", "").strip(),
                actual_status=row.get("actual_status", "").strip() or "UNKNOWN",
                actual_progress=self._parse_progress(row.get("actual_progress", "")),
                last_report_id=row.get("last_report_id", "").strip() or None,
                last_update_timestamp=row.get("last_update_timestamp", "").strip() or None,
            )
            if record.activity_id:
                self._cache[record.activity_id] = record

        self._loaded = True
        logger.debug("Loaded %d execution state records", len(self._cache))

    @staticmethod
    def _parse_progress(value: str) -> Optional[float]:
        """Parse progress value from CSV string."""
        if not value or value.strip() == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _write_all(self) -> None:
        """Write all cached records to CSV."""
        path = Path(self.config.execution_state_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EXECUTION_STATE_COLUMNS)
            writer.writeheader()
            for record in self._cache.values():
                writer.writerow(record.to_dict())

        logger.debug("Wrote %d execution state records", len(self._cache))

    def get(self, activity_id: str) -> Optional[ExecutionState]:
        """Get execution state for an activity.

        Returns None if the activity has no execution state yet (fresh activity).
        """
        self._load_all()
        record = self._cache.get(activity_id)
        if record is None:
            return None
        return record.to_execution_state()

    def save(self, state: ExecutionState) -> None:
        """Save or update execution state for an activity."""
        self._load_all()

        record = ExecutionStateRecord.from_execution_state(state)
        self._cache[record.activity_id] = record
        self._write_all()

        logger.info(
            "Saved execution state: activity_id=%s status=%s progress=%s report_id=%s",
            state.activity_id,
            state.actual_status.value,
            state.actual_progress,
            state.last_report_id,
        )

    def exists(self, activity_id: str) -> bool:
        """Check if execution state exists for an activity."""
        self._load_all()
        return activity_id in self._cache

    def get_all(self) -> List[ExecutionState]:
        """Get all execution states."""
        self._load_all()
        return [r.to_execution_state() for r in self._cache.values()]

    def clear_cache(self) -> None:
        """Clear in-memory cache and allow reloading from file (useful for testing)."""
        self._cache.clear()
        self._loaded = False