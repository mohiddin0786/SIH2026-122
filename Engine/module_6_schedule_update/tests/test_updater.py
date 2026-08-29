"""
module_6_schedule_update/tests/test_updater.py

Unit tests for ScheduleUpdater - the core Schedule Update Engine.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from shared.constants import (
    ActivityType,
    DecisionType,
    EventType,
    ExecutionStatus,
    UpdateStatus,
)
from shared.exceptions import ScheduleUpdateError
from shared.schemas import (
    ActivityTypeValue,
    DecisionResult,
    EventTypeValue,
    ExtractedNumericValue,
    ExtractedReport,
    ExtractedEntity,
    UpdateResult,
)

from module_6_schedule_update.config import ScheduleUpdateConfig
from module_6_schedule_update.updater import ScheduleUpdater, update_schedule


# ============================================================
# Test fixtures and helpers
# ============================================================

def _make_decision(
    report_id: str,
    decision: DecisionType,
    selected_activity_id: str | None = None,
    confidence: float = 0.95,
    decision_reasons: list[str] | None = None,
) -> DecisionResult:
    """Create a DecisionResult for testing."""
    return DecisionResult(
        report_id=report_id,
        decision=decision,
        selected_activity_id=selected_activity_id,
        confidence=confidence,
        decision_reasons=decision_reasons or [],
    )


def _make_extracted_report(
    report_id: str,
    event_type: EventType,
    progress: float | None = None,
    equipment: list[str] | None = None,
    activity_type: ActivityType = ActivityType.INSTALL,
) -> ExtractedReport:
    """Create an ExtractedReport for testing."""
    return ExtractedReport(
        report_id=report_id,
        normalized_text="Test report",
        equipment_tags=[ExtractedEntity(value=e, confidence=0.9) for e in (equipment or [])],
        locations=[],
        activity_type=ActivityTypeValue(value=activity_type, confidence=0.9),
        event_type=EventTypeValue(value=event_type, confidence=0.9),
        progress=ExtractedNumericValue(value=progress, confidence=0.9 if progress is not None else 0.0),
    )


@pytest.fixture
def temp_config():
    """Create a config with temporary execution state file."""
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / "execution_state.csv"
    config = ScheduleUpdateConfig(
        execution_state_path=str(temp_path),
        schedule_master_path="Data/schedule_master_v1.csv",
        auto_create_execution_store=True,
    )
    yield config
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()
    os.rmdir(temp_dir)


@pytest.fixture
def schedule_master_df():
    """Load actual Schedule Master for testing."""
    return pd.read_csv("Data/schedule_master_v1.csv", dtype=str)


@pytest.fixture
def updater(temp_config, schedule_master_df):
    """Create a ScheduleUpdater with temp config and real schedule master."""
    return ScheduleUpdater(config=temp_config, schedule_master_df=schedule_master_df)


# ============================================================
# Test 1: AUTO_MATCH + START → IN_PROGRESS, 0%
# ============================================================

def test_auto_match_start(updater):
    """AUTO_MATCH with START event sets IN_PROGRESS, 0%."""
    decision = _make_decision("RPT-001", DecisionType.AUTO_MATCH, "CIV-001")
    extracted = _make_extracted_report("RPT-001", EventType.START)

    result = updater.update_schedule(decision, extracted)

    assert result.report_id == "RPT-001"
    assert result.update_status == UpdateStatus.UPDATED
    assert result.activity_id == "CIV-001"
    assert result.new_execution_state is not None
    assert result.new_execution_state.actual_status == ExecutionStatus.IN_PROGRESS
    assert result.new_execution_state.actual_progress == 0.0
    assert result.new_execution_state.last_report_id == "RPT-001"
    assert "START" in result.update_reason


# ============================================================
# Test 2: AUTO_MATCH + PROGRESS 50% → IN_PROGRESS, 50%
# ============================================================

def test_auto_match_progress(updater):
    """AUTO_MATCH with PROGRESS event sets IN_PROGRESS with extracted progress."""
    decision = _make_decision("RPT-002", DecisionType.AUTO_MATCH, "CIV-001")
    extracted = _make_extracted_report("RPT-002", EventType.PROGRESS, progress=50.0)

    result = updater.update_schedule(decision, extracted)

    assert result.update_status == UpdateStatus.UPDATED
    assert result.new_execution_state.actual_status == ExecutionStatus.IN_PROGRESS
    assert result.new_execution_state.actual_progress == 50.0


# ============================================================
# Test 3: AUTO_MATCH + FINISH → COMPLETED, 100%
# ============================================================

def test_auto_match_finish(updater):
    """AUTO_MATCH with FINISH event sets COMPLETED, 100%."""
    decision = _make_decision("RPT-003", DecisionType.AUTO_MATCH, "CIV-001")
    extracted = _make_extracted_report("RPT-003", EventType.FINISH)

    result = updater.update_schedule(decision, extracted)

    assert result.update_status == UpdateStatus.UPDATED
    assert result.new_execution_state.actual_status == ExecutionStatus.COMPLETED
    assert result.new_execution_state.actual_progress == 100.0


# ============================================================
# Test 4: HUMAN_REVIEW → PENDING_REVIEW, no update
# ============================================================

def test_human_review_no_update(updater):
    """HUMAN_REVIEW returns PENDING_REVIEW without updating state."""
    decision = _make_decision("RPT-004", DecisionType.HUMAN_REVIEW, "CIV-001")
    extracted = _make_extracted_report("RPT-004", EventType.FINISH)

    result = updater.update_schedule(decision, extracted)

    assert result.update_status == UpdateStatus.PENDING_REVIEW
    assert result.activity_id == "CIV-001"
    assert result.new_execution_state is None
    assert result.previous_execution_state is None
    assert "human review" in result.update_reason.lower()


# ============================================================
# Test 5: UNMATCHED → NO_UPDATE, no update
# ============================================================

def test_unmatched_no_update(updater):
    """UNMATCHED returns NO_UPDATE without updating state."""
    decision = _make_decision("RPT-005", DecisionType.UNMATCHED, None)
    extracted = _make_extracted_report("RPT-005", EventType.FINISH)

    result = updater.update_schedule(decision, extracted)

    assert result.update_status == UpdateStatus.NO_UPDATE
    assert result.activity_id is None
    assert result.new_execution_state is None
    assert "no activity" in result.update_reason.lower()


# ============================================================
# Test 6: Invalid activity ID → NO_UPDATE with clear reason
# ============================================================

def test_invalid_activity_id(updater):
    """AUTO_MATCH with non-existent activity returns NO_UPDATE."""
    decision = _make_decision("RPT-006", DecisionType.AUTO_MATCH, "NONEXISTENT-999")
    extracted = _make_extracted_report("RPT-006", EventType.FINISH)

    result = updater.update_schedule(decision, extracted)

    assert result.update_status == UpdateStatus.NO_UPDATE
    assert result.activity_id == "NONEXISTENT-999"
    assert result.new_execution_state is None
    assert "does not exist" in result.update_reason


# ============================================================
# Test 7: Invalid progress below 0 → validation error
# ============================================================

def test_invalid_progress_below_zero(updater):
    """Progress below 0 is rejected by schema validation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExtractedNumericValue(value=-10.0, confidence=0.9)


# ============================================================
# Test 8: Invalid progress above 100 → validation error
# ============================================================

def test_invalid_progress_above_100(updater):
    """Progress above 100 is rejected by schema validation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExtractedNumericValue(value=150.0, confidence=0.9)


# ============================================================
# Test 9: Duplicate report → idempotent behavior
# ============================================================

def test_duplicate_report_idempotent(updater):
    """Processing same report twice is idempotent."""
    decision = _make_decision("RPT-007", DecisionType.AUTO_MATCH, "CIV-001")
    extracted = _make_extracted_report("RPT-007", EventType.FINISH)

    # First update
    result1 = updater.update_schedule(decision, extracted)
    assert result1.update_status == UpdateStatus.UPDATED
    assert result1.new_execution_state.actual_status == ExecutionStatus.COMPLETED

    # Second update with same report_id
    result2 = updater.update_schedule(decision, extracted)
    assert result2.update_status == UpdateStatus.UPDATED
    assert result2.new_execution_state.actual_status == ExecutionStatus.COMPLETED
    assert result2.new_execution_state.actual_progress == 100.0
    assert "already processed" in result2.update_reason.lower()


# ============================================================
# Test 10: COMPLETED activity receives older PROGRESS → no regression
# ============================================================

def test_completed_regression_blocked(updater):
    """COMPLETED activity receiving older PROGRESS report is blocked."""
    # First, complete the activity
    decision_finish = _make_decision("RPT-008", DecisionType.AUTO_MATCH, "CIV-001")
    extracted_finish = _make_extracted_report("RPT-008", EventType.FINISH)
    result1 = updater.update_schedule(decision_finish, extracted_finish)
    assert result1.new_execution_state.actual_status == ExecutionStatus.COMPLETED

    # Then try to update with an older PROGRESS report
    decision_progress = _make_decision("RPT-009", DecisionType.AUTO_MATCH, "CIV-001")
    extracted_progress = _make_extracted_report("RPT-009", EventType.PROGRESS, progress=50.0)
    result2 = updater.update_schedule(decision_progress, extracted_progress)

    assert result2.update_status == UpdateStatus.NO_UPDATE
    assert result2.new_execution_state is None
    assert "regression blocked" in result2.update_reason.lower()

    # State should still be COMPLETED
    current = updater.repository.get("CIV-001")
    assert current.actual_status == ExecutionStatus.COMPLETED
    assert current.actual_progress == 100.0


# ============================================================
# Test 11: Baseline protection - Schedule Master unchanged
# ============================================================

def test_baseline_protection(updater, schedule_master_df):
    """Schedule Master baseline fields remain unchanged after update."""
    # Get baseline before
    baseline_before = schedule_master_df[schedule_master_df["activity_id"] == "CIV-001"].iloc[0]
    planned_start_before = baseline_before["planned_start"]
    planned_finish_before = baseline_before["planned_finish"]
    planned_duration_before = baseline_before["planned_duration_days"]
    baseline_status_before = baseline_before["baseline_status"]

    # Perform update
    decision = _make_decision("RPT-010", DecisionType.AUTO_MATCH, "CIV-001")
    extracted = _make_extracted_report("RPT-010", EventType.FINISH)
    updater.update_schedule(decision, extracted)

    # Verify Schedule Master unchanged (should be same DataFrame reference)
    baseline_after = schedule_master_df[schedule_master_df["activity_id"] == "CIV-001"].iloc[0]
    assert baseline_after["planned_start"] == planned_start_before
    assert baseline_after["planned_finish"] == planned_finish_before
    assert baseline_after["planned_duration_days"] == planned_duration_before
    assert baseline_after["baseline_status"] == baseline_status_before


# ============================================================
# Test 12: Fresh execution store initializes correctly
# ============================================================

def test_fresh_store_initialization(temp_config):
    """Fresh execution store initializes correctly on first use."""
    # Don't pre-create the file - let updater create it
    updater = ScheduleUpdater(config=temp_config)

    decision = _make_decision("RPT-011", DecisionType.AUTO_MATCH, "CIV-001")
    extracted = _make_extracted_report("RPT-011", EventType.START)
    result = updater.update_schedule(decision, extracted)

    assert result.update_status == UpdateStatus.UPDATED
    assert result.new_execution_state is not None

    # Verify file was created
    assert Path(temp_config.execution_state_path).exists()


# ============================================================
# Test 13: UpdateResult conforms to schema
# ============================================================

def test_update_result_schema_validation(updater):
    """Returned UpdateResult conforms to shared schema."""
    decision = _make_decision("RPT-012", DecisionType.AUTO_MATCH, "CIV-001")
    extracted = _make_extracted_report("RPT-012", EventType.FINISH)

    result = updater.update_schedule(decision, extracted)

    # Should be a valid UpdateResult (already validated by pydantic)
    assert isinstance(result, UpdateResult)
    assert result.report_id == "RPT-012"
    assert result.update_status in (UpdateStatus.UPDATED, UpdateStatus.PENDING_REVIEW, UpdateStatus.NO_UPDATE)
    if result.activity_id:
        assert isinstance(result.activity_id, str)


# ============================================================
# Additional: Progress preservation on PROGRESS without percentage
# ============================================================

def test_progress_preserves_existing_when_no_percentage(updater):
    """PROGRESS without percentage preserves existing progress."""
    # First set to 60%
    decision1 = _make_decision("RPT-013", DecisionType.AUTO_MATCH, "CIV-001")
    extracted1 = _make_extracted_report("RPT-013", EventType.PROGRESS, progress=60.0)
    updater.update_schedule(decision1, extracted1)

    # Then PROGRESS without percentage
    decision2 = _make_decision("RPT-014", DecisionType.AUTO_MATCH, "CIV-001")
    extracted2 = _make_extracted_report("RPT-014", EventType.PROGRESS, progress=None)
    result = updater.update_schedule(decision2, extracted2)

    assert result.new_execution_state.actual_progress == 60.0


# ============================================================
# Additional: State transitions work correctly
# ============================================================

def test_state_transitions(updater):
    """Test full lifecycle: START → PROGRESS → FINISH."""
    # START
    r1 = updater.update_schedule(
        _make_decision("RPT-015", DecisionType.AUTO_MATCH, "CIV-001"),
        _make_extracted_report("RPT-015", EventType.START),
    )
    assert r1.new_execution_state.actual_status == ExecutionStatus.IN_PROGRESS
    assert r1.new_execution_state.actual_progress == 0.0

    # PROGRESS 30%
    r2 = updater.update_schedule(
        _make_decision("RPT-016", DecisionType.AUTO_MATCH, "CIV-001"),
        _make_extracted_report("RPT-016", EventType.PROGRESS, progress=30.0),
    )
    assert r2.new_execution_state.actual_status == ExecutionStatus.IN_PROGRESS
    assert r2.new_execution_state.actual_progress == 30.0

    # PROGRESS 80%
    r3 = updater.update_schedule(
        _make_decision("RPT-017", DecisionType.AUTO_MATCH, "CIV-001"),
        _make_extracted_report("RPT-017", EventType.PROGRESS, progress=80.0),
    )
    assert r3.new_execution_state.actual_progress == 80.0

    # FINISH
    r4 = updater.update_schedule(
        _make_decision("RPT-018", DecisionType.AUTO_MATCH, "CIV-001"),
        _make_extracted_report("RPT-018", EventType.FINISH),
    )
    assert r4.new_execution_state.actual_status == ExecutionStatus.COMPLETED
    assert r4.new_execution_state.actual_progress == 100.0


# ============================================================
# Additional: AUTO_MATCH requires extracted_report
# ============================================================

def test_auto_match_requires_extracted_report(updater):
    """AUTO_MATCH without extracted_report returns NO_UPDATE with reason."""
    decision = _make_decision("RPT-019", DecisionType.AUTO_MATCH, "CIV-001")
    result = updater.update_schedule(decision, extracted_report=None)

    assert result.update_status == UpdateStatus.NO_UPDATE
    assert "requires extracted_report" in result.update_reason


# ============================================================
# Additional: Decision validation (tested at schema level)
# ============================================================

def test_auto_match_requires_selection():
    """AUTO_MATCH without selected_activity_id is rejected by DecisionResult schema."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        _make_decision("RPT-020", DecisionType.AUTO_MATCH, selected_activity_id=None)


def test_unmatched_forbids_selection():
    """UNMATCHED with selected_activity_id is rejected by DecisionResult schema."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        _make_decision("RPT-021", DecisionType.UNMATCHED, selected_activity_id="CIV-001")


# ============================================================
# Convenience function test
# ============================================================

def test_convenience_function(temp_config):
    """Test the update_schedule convenience function."""
    result = update_schedule(
        decision=_make_decision("RPT-022", DecisionType.AUTO_MATCH, "CIV-001"),
        extracted_report=_make_extracted_report("RPT-022", EventType.FINISH),
        config=temp_config,
    )
    assert result.update_status == UpdateStatus.UPDATED
    assert result.activity_id == "CIV-001"