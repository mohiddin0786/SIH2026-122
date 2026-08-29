"""
module_6_schedule_update/tests/test_repository.py

Unit tests for ExecutionStateRepository - execution state persistence.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from shared.constants import ExecutionStatus
from shared.schemas import ExecutionState

from module_6_schedule_update.config import ScheduleUpdateConfig
from module_6_schedule_update.repository import ExecutionStateRepository, ExecutionStateRecord


class TestExecutionStateRepository:
    """Tests for ExecutionStateRepository."""

    def setup_method(self):
        # Use a temp file for each test
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir) / "execution_state.csv"
        self.config = ScheduleUpdateConfig(
            execution_state_path=str(self.temp_path),
            schedule_master_path="Data/schedule_master_v1.csv",
            auto_create_execution_store=True,
        )
        self.repo = ExecutionStateRepository(self.config)

    def teardown_method(self):
        # Clean up temp file
        if self.temp_path.exists():
            self.temp_path.unlink()
        os.rmdir(self.temp_dir)

    def test_fresh_store_returns_none(self):
        """Getting state for unknown activity returns None."""
        result = self.repo.get("NONEXISTENT-001")
        assert result is None

    def test_save_and_get_roundtrip(self):
        """Save and retrieve execution state."""
        state = ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.IN_PROGRESS,
            actual_progress=50.0,
            last_report_id="RPT-0001",
            last_update_timestamp="2026-01-07T10:00:00Z",
        )
        self.repo.save(state)

        retrieved = self.repo.get("CIV-001")
        assert retrieved is not None
        assert retrieved.activity_id == "CIV-001"
        assert retrieved.actual_status == ExecutionStatus.IN_PROGRESS
        assert retrieved.actual_progress == 50.0
        assert retrieved.last_report_id == "RPT-0001"
        assert retrieved.last_update_timestamp == "2026-01-07T10:00:00Z"

    def test_update_existing_state(self):
        """Updating existing state overwrites it."""
        initial = ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.NOT_STARTED,
            actual_progress=0.0,
            last_report_id="RPT-0001",
            last_update_timestamp="2026-01-05T10:00:00Z",
        )
        self.repo.save(initial)

        updated = ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.IN_PROGRESS,
            actual_progress=25.0,
            last_report_id="RPT-0002",
            last_update_timestamp="2026-01-06T10:00:00Z",
        )
        self.repo.save(updated)

        retrieved = self.repo.get("CIV-001")
        assert retrieved.actual_status == ExecutionStatus.IN_PROGRESS
        assert retrieved.actual_progress == 25.0
        assert retrieved.last_report_id == "RPT-0002"

    def test_multiple_activities_independent(self):
        """Different activities have independent state."""
        self.repo.save(ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.COMPLETED,
            actual_progress=100.0,
            last_report_id="RPT-001",
            last_update_timestamp="2026-01-07T10:00:00Z",
        ))
        self.repo.save(ExecutionState(
            activity_id="MEC-004",
            actual_status=ExecutionStatus.IN_PROGRESS,
            actual_progress=50.0,
            last_report_id="RPT-002",
            last_update_timestamp="2026-01-20T10:00:00Z",
        ))

        civ = self.repo.get("CIV-001")
        mec = self.repo.get("MEC-004")

        assert civ.actual_status == ExecutionStatus.COMPLETED
        assert mec.actual_status == ExecutionStatus.IN_PROGRESS
        assert civ.actual_progress == 100.0
        assert mec.actual_progress == 50.0

    def test_exists(self):
        """exists() returns True for saved activities."""
        assert not self.repo.exists("CIV-001")
        self.repo.save(ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.IN_PROGRESS,
            actual_progress=10.0,
            last_report_id="RPT-001",
            last_update_timestamp="2026-01-05T10:00:00Z",
        ))
        assert self.repo.exists("CIV-001")

    def test_get_all(self):
        """get_all returns all saved states."""
        self.repo.save(ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.IN_PROGRESS,
            actual_progress=10.0,
            last_report_id="RPT-001",
            last_update_timestamp="2026-01-05T10:00:00Z",
        ))
        self.repo.save(ExecutionState(
            activity_id="MEC-004",
            actual_status=ExecutionStatus.NOT_STARTED,
            actual_progress=0.0,
            last_report_id="RPT-002",
            last_update_timestamp="2026-01-20T10:00:00Z",
        ))

        all_states = self.repo.get_all()
        assert len(all_states) == 2
        ids = {s.activity_id for s in all_states}
        assert ids == {"CIV-001", "MEC-004"}

    def test_persists_to_csv(self):
        """Data actually persists to CSV file."""
        state = ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.IN_PROGRESS,
            actual_progress=50.0,
            last_report_id="RPT-0001",
            last_update_timestamp="2026-01-07T10:00:00Z",
        )
        self.repo.save(state)

        # Create new repo instance pointing to same file
        new_repo = ExecutionStateRepository(self.config)
        retrieved = new_repo.get("CIV-001")

        assert retrieved is not None
        assert retrieved.activity_id == "CIV-001"
        assert retrieved.actual_progress == 50.0

    def test_handles_missing_progress(self):
        """Progress can be None."""
        state = ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.IN_PROGRESS,
            actual_progress=None,
            last_report_id="RPT-0001",
            last_update_timestamp="2026-01-07T10:00:00Z",
        )
        self.repo.save(state)

        retrieved = self.repo.get("CIV-001")
        assert retrieved.actual_progress is None

    def test_clear_cache(self):
        """clear_cache forces reload from disk."""
        self.repo.save(ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.IN_PROGRESS,
            actual_progress=10.0,
            last_report_id="RPT-001",
            last_update_timestamp="2026-01-05T10:00:00Z",
        ))

        self.repo.clear_cache()
        # Should still retrieve from disk
        retrieved = self.repo.get("CIV-001")
        assert retrieved is not None
        assert retrieved.actual_progress == 10.0


class TestExecutionStateRecord:
    """Tests for ExecutionStateRecord conversion."""

    def test_to_execution_state(self):
        record = ExecutionStateRecord(
            activity_id="CIV-001",
            actual_status="IN_PROGRESS",
            actual_progress=50.0,
            last_report_id="RPT-001",
            last_update_timestamp="2026-01-07T10:00:00Z",
        )
        state = record.to_execution_state()
        assert state.activity_id == "CIV-001"
        assert state.actual_status == ExecutionStatus.IN_PROGRESS
        assert state.actual_progress == 50.0

    def test_from_execution_state(self):
        state = ExecutionState(
            activity_id="CIV-001",
            actual_status=ExecutionStatus.COMPLETED,
            actual_progress=100.0,
            last_report_id="RPT-001",
            last_update_timestamp="2026-01-07T10:00:00Z",
        )
        record = ExecutionStateRecord.from_execution_state(state)
        assert record.activity_id == "CIV-001"
        assert record.actual_status == "COMPLETED"
        assert record.actual_progress == 100.0

    def test_to_dict_for_csv(self):
        record = ExecutionStateRecord(
            activity_id="CIV-001",
            actual_status="IN_PROGRESS",
            actual_progress=50.0,
            last_report_id="RPT-001",
            last_update_timestamp="2026-01-07T10:00:00Z",
        )
        d = record.to_dict()
        assert d["activity_id"] == "CIV-001"
        assert d["actual_status"] == "IN_PROGRESS"
        assert d["actual_progress"] == 50.0
        assert d["last_report_id"] == "RPT-001"