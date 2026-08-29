"""
module_6_schedule_update/tests/test_status_mapper.py

Unit tests for StatusMapper - event to execution status mapping.
"""

from __future__ import annotations

import pytest

from shared.constants import EventType, ExecutionStatus
from shared.schemas import (
    ActivityTypeValue,
    EventTypeValue,
    ExtractedNumericValue,
    ExtractedReport,
    ExtractedEntity,
)

from module_6_schedule_update.status_mapper import StatusMapper, DEFAULT_STATUS_MAPPER


class TestStatusMapper:
    """Tests for StatusMapper.map_event"""

    def setup_method(self):
        self.mapper = StatusMapper()

    # --- START event ---
    def test_start_event_maps_to_in_progress_zero_progress(self):
        result = self.mapper.map_event(EventType.START, extracted_progress=None)
        assert result.actual_status == ExecutionStatus.IN_PROGRESS
        assert result.actual_progress == 0.0
        assert "START" in result.reason
        assert "IN_PROGRESS" in result.reason

    def test_start_event_ignores_extracted_progress(self):
        # Even if extraction found a progress, START means 0%
        result = self.mapper.map_event(EventType.START, extracted_progress=50.0)
        assert result.actual_progress == 0.0

    # --- PROGRESS event ---
    def test_progress_event_with_percentage(self):
        result = self.mapper.map_event(EventType.PROGRESS, extracted_progress=60.0)
        assert result.actual_status == ExecutionStatus.IN_PROGRESS
        assert result.actual_progress == 60.0
        assert "60" in result.reason

    def test_progress_event_without_percentage_preserves_current(self):
        result = self.mapper.map_event(
            EventType.PROGRESS,
            extracted_progress=None,
            current_progress=45.0,
        )
        assert result.actual_status == ExecutionStatus.IN_PROGRESS
        assert result.actual_progress == 45.0
        assert "45" in result.reason

    def test_progress_event_without_percentage_and_no_current(self):
        result = self.mapper.map_event(
            EventType.PROGRESS,
            extracted_progress=None,
            current_progress=None,
        )
        assert result.actual_status == ExecutionStatus.IN_PROGRESS
        assert result.actual_progress is None

    # --- FINISH event ---
    def test_finish_event_maps_to_completed_100(self):
        result = self.mapper.map_event(EventType.FINISH, extracted_progress=None)
        assert result.actual_status == ExecutionStatus.COMPLETED
        assert result.actual_progress == 100.0
        assert "FINISH" in result.reason
        assert "COMPLETED" in result.reason

    def test_finish_event_ignores_extracted_progress(self):
        # FINISH always means 100%
        result = self.mapper.map_event(EventType.FINISH, extracted_progress=50.0)
        assert result.actual_progress == 100.0

    # --- UNKNOWN event ---
    def test_unknown_event_preserves_current_state(self):
        result = self.mapper.map_event(
            EventType.UNKNOWN,
            extracted_progress=None,
            current_state=ExecutionStatus.IN_PROGRESS,
            current_progress=30.0,
        )
        assert result.actual_status == ExecutionStatus.IN_PROGRESS
        assert result.actual_progress == 30.0
        assert "unchanged" in result.reason.lower()

    def test_unknown_event_with_no_current(self):
        result = self.mapper.map_event(EventType.UNKNOWN, extracted_progress=None)
        assert result.actual_status == ExecutionStatus.UNKNOWN
        assert result.actual_progress is None


class TestStatusMapperFromExtractedReport:
    """Tests for StatusMapper.map_from_extracted_report"""

    def setup_method(self):
        self.mapper = StatusMapper()

    def _make_report(
        self,
        event_type: EventType,
        progress: float | None = None,
    ) -> ExtractedReport:
        return ExtractedReport(
            report_id="TEST-001",
            normalized_text="Test report",
            equipment_tags=[],
            locations=[],
            activity_type=ActivityTypeValue(),
            event_type=EventTypeValue(value=event_type, confidence=0.9),
            progress=ExtractedNumericValue(value=progress, confidence=0.9 if progress is not None else 0.0),
        )

    def test_start_from_report(self):
        report = self._make_report(EventType.START)
        result = self.mapper.map_from_extracted_report(report)
        assert result.actual_status == ExecutionStatus.IN_PROGRESS
        assert result.actual_progress == 0.0

    def test_progress_from_report(self):
        report = self._make_report(EventType.PROGRESS, 75.0)
        result = self.mapper.map_from_extracted_report(report)
        assert result.actual_status == ExecutionStatus.IN_PROGRESS
        assert result.actual_progress == 75.0

    def test_finish_from_report(self):
        report = self._make_report(EventType.FINISH)
        result = self.mapper.map_from_extracted_report(report)
        assert result.actual_status == ExecutionStatus.COMPLETED
        assert result.actual_progress == 100.0

    def test_unknown_from_report(self):
        report = self._make_report(EventType.UNKNOWN)
        result = self.mapper.map_from_extracted_report(report)
        assert result.actual_status == ExecutionStatus.UNKNOWN
        assert result.actual_progress is None


class TestDefaultStatusMapper:
    """Test the default singleton instance works."""

    def test_default_instance_exists(self):
        assert DEFAULT_STATUS_MAPPER is not None
        result = DEFAULT_STATUS_MAPPER.map_event(EventType.FINISH, None)
        assert result.actual_status == ExecutionStatus.COMPLETED