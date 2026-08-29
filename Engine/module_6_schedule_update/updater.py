"""
module_6_schedule_update/updater.py — Core Schedule Update Engine.

Converts DecisionResult + execution information into updated ExecutionState
and returns a structured UpdateResult. Pure business logic, no persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from shared.constants import DecisionType, UpdateStatus, ExecutionStatus
from shared.exceptions import ScheduleUpdateError
from shared.schemas import (
    DecisionResult,
    ExecutionState,
    UpdateResult,
    ExtractedReport,
)

from .config import ScheduleUpdateConfig, DEFAULT_CONFIG
from .repository import ExecutionStateRepository
from .status_mapper import StatusMapper, DEFAULT_STATUS_MAPPER

logger = logging.getLogger(__name__)


class ScheduleUpdater:
    """Main entry point for the Schedule Update Engine."""

    def __init__(
        self,
        config: Optional[ScheduleUpdateConfig] = None,
        repository: Optional[ExecutionStateRepository] = None,
        status_mapper: Optional[StatusMapper] = None,
        schedule_master_df: Optional[pd.DataFrame] = None,
    ):
        self.config = config or DEFAULT_CONFIG
        self.repository = repository or ExecutionStateRepository(self.config)
        self.status_mapper = status_mapper or DEFAULT_STATUS_MAPPER
        self._schedule_master = schedule_master_df
        self._schedule_master_path = self.config.schedule_master_path

    def _load_schedule_master(self) -> pd.DataFrame:
        """Load and cache the Schedule Master DataFrame."""
        if self._schedule_master is not None:
            return self._schedule_master

        df = pd.read_csv(self._schedule_master_path, dtype=str)
        # Validate required columns exist
        required = ["activity_id", "planned_start", "planned_finish", "planned_duration_days", "baseline_status"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ScheduleUpdateError(
                f"Schedule Master missing required columns: {missing}",
                report_id="N/A",
            )
        self._schedule_master = df
        return df

    def _get_activity_baseline(self, activity_id: str) -> Optional[pd.Series]:
        """Get baseline info for an activity from Schedule Master.

        Returns None if activity doesn't exist.
        """
        df = self._load_schedule_master()
        matches = df[df["activity_id"] == activity_id]
        if matches.empty:
            return None
        return matches.iloc[0]

    def _validate_decision(self, decision: DecisionResult) -> None:
        """Validate decision input against schema rules.

        These rules are also enforced by DecisionResult validators, but we
        double-check here for defense-in-depth.
        """
        if decision.decision == DecisionType.AUTO_MATCH and not decision.selected_activity_id:
            raise ScheduleUpdateError(
                "AUTO_MATCH decision requires selected_activity_id",
                report_id=decision.report_id,
            )
        if decision.decision == DecisionType.UNMATCHED and decision.selected_activity_id is not None:
            raise ScheduleUpdateError(
                "UNMATCHED decision must have selected_activity_id = None",
                report_id=decision.report_id,
            )

    def _check_duplicate_report(
        self,
        activity_id: str,
        report_id: str,
        new_timestamp: str,
    ) -> bool:
        """Check if this report has already been processed for this activity.

        Returns True if this is a duplicate (same report_id already recorded).
        """
        current = self.repository.get(activity_id)
        if current and current.last_report_id == report_id:
            logger.info(
                "Duplicate report detected: activity_id=%s report_id=%s (already processed)",
                activity_id,
                report_id,
            )
            return True
        return False

    def _should_allow_regression(
        self,
        current_status: str,
        new_status: str,
    ) -> bool:
        """Determine if state regression is allowed.

        By default, prevent COMPLETED → IN_PROGRESS regression.
        """
        if self.config.allow_state_regression:
            return True

        # Prevent COMPLETED from going back to IN_PROGRESS
        if current_status == ExecutionStatus.COMPLETED.value and new_status == ExecutionStatus.IN_PROGRESS.value:
            logger.warning(
                "State regression blocked: %s → %s (config.allow_state_regression=False)",
                current_status,
                new_status,
            )
            return False

        return True

    def update_schedule(
        self,
        decision: DecisionResult,
        extracted_report: Optional[ExtractedReport] = None,
    ) -> UpdateResult:
        """Main entry point: update schedule based on decision and execution info.

        Args:
            decision: DecisionResult from Module 5 (Decision Engine).
            extracted_report: Optional ExtractedReport for event/progress info.
                Required for AUTO_MATCH to determine the event type and progress.

        Returns:
            UpdateResult with the outcome of the update attempt.
        """
        self._validate_decision(decision)

        # Handle non-AUTO_MATCH decisions first (no schedule update)
        if decision.decision == DecisionType.HUMAN_REVIEW:
            return self._handle_human_review(decision)

        if decision.decision == DecisionType.UNMATCHED:
            return self._handle_unmatched(decision)

        # AUTO_MATCH: proceed with update
        return self._handle_auto_match(decision, extracted_report)

    def _handle_human_review(self, decision: DecisionResult) -> UpdateResult:
        """Handle HUMAN_REVIEW decision - no automatic update."""
        activity_id = decision.selected_activity_id
        reason = (
            f"Decision requires human review. "
            f"Leading candidate: {activity_id or 'none'}. "
            f"Confidence: {decision.confidence:.2f}. "
            f"Reasons: {', '.join(decision.decision_reasons) if decision.decision_reasons else 'none'}"
        )

        return UpdateResult(
            report_id=decision.report_id,
            update_status=UpdateStatus.PENDING_REVIEW,
            activity_id=activity_id,
            previous_execution_state=None,
            new_execution_state=None,
            update_reason=reason,
        )

    def _handle_unmatched(self, decision: DecisionResult) -> UpdateResult:
        """Handle UNMATCHED decision - no update."""
        reason = (
            f"No activity could be confidently matched. "
            f"Confidence: {decision.confidence:.2f}. "
            f"Reasons: {', '.join(decision.decision_reasons) if decision.decision_reasons else 'none'}"
        )

        return UpdateResult(
            report_id=decision.report_id,
            update_status=UpdateStatus.NO_UPDATE,
            activity_id=None,
            previous_execution_state=None,
            new_execution_state=None,
            update_reason=reason,
        )

    def _handle_auto_match(
        self,
        decision: DecisionResult,
        extracted_report: Optional[ExtractedReport],
    ) -> UpdateResult:
        """Handle AUTO_MATCH decision - update execution state."""
        activity_id = decision.selected_activity_id
        report_id = decision.report_id

        if not activity_id:
            raise ScheduleUpdateError(
                "AUTO_MATCH missing selected_activity_id",
                report_id=report_id,
            )

        # Verify activity exists in Schedule Master (baseline)
        baseline = self._get_activity_baseline(activity_id)
        if baseline is None:
            reason = f"Selected activity {activity_id} does not exist in Schedule Master"
            logger.error("Invalid activity_id: %s for report_id: %s", activity_id, report_id)
            return UpdateResult(
                report_id=report_id,
                update_status=UpdateStatus.NO_UPDATE,
                activity_id=activity_id,
                previous_execution_state=None,
                new_execution_state=None,
                update_reason=reason,
            )

        # Get current execution state
        previous_state = self.repository.get(activity_id)

        # Check for duplicate report
        timestamp = datetime.now(timezone.utc).strftime(self.config.timestamp_format)
        if self._check_duplicate_report(activity_id, report_id, timestamp):
            # Return current state as "no change" but with UPDATED status to indicate
            # the request was valid but already applied
            return UpdateResult(
                report_id=report_id,
                update_status=UpdateStatus.UPDATED,
                activity_id=activity_id,
                previous_execution_state=previous_state,
                new_execution_state=previous_state,
                update_reason=f"Report {report_id} already processed for this activity (idempotent)",
            )

        # Determine event and progress from extracted report
        if extracted_report is None:
            reason = "AUTO_MATCH requires extracted_report for event/progress information"
            logger.error("Missing extracted_report for AUTO_MATCH: %s", report_id)
            return UpdateResult(
                report_id=report_id,
                update_status=UpdateStatus.NO_UPDATE,
                activity_id=activity_id,
                previous_execution_state=previous_state,
                new_execution_state=None,
                update_reason=reason,
            )

        # Map event to status and progress
        current_status = previous_state.actual_status if previous_state else None
        current_progress = previous_state.actual_progress if previous_state else None

        mapping = self.status_mapper.map_from_extracted_report(
            extracted_report,
            current_state=current_status,
            current_progress=current_progress,
        )

        # Check for state regression
        if previous_state and not self._should_allow_regression(
            previous_state.actual_status.value,
            mapping.actual_status.value,
        ):
            return UpdateResult(
                report_id=report_id,
                update_status=UpdateStatus.NO_UPDATE,
                activity_id=activity_id,
                previous_execution_state=previous_state,
                new_execution_state=None,
                update_reason=(
                    f"State regression blocked: {previous_state.actual_status.value} "
                    f"→ {mapping.actual_status.value}. "
                    f"Report {report_id} would revert COMPLETED activity."
                ),
            )

        # Build new execution state
        new_state = ExecutionState(
            activity_id=activity_id,
            actual_status=mapping.actual_status,
            actual_progress=mapping.actual_progress,
            last_report_id=report_id,
            last_update_timestamp=timestamp,
        )

        # Persist
        self.repository.save(new_state)

        return UpdateResult(
            report_id=report_id,
            update_status=UpdateStatus.UPDATED,
            activity_id=activity_id,
            previous_execution_state=previous_state,
            new_execution_state=new_state,
            update_reason=f"AUTO_MATCH: {mapping.reason}. Confidence: {decision.confidence:.2f}",
        )


# Convenience function for simple usage
def update_schedule(
    decision: DecisionResult,
    extracted_report: Optional[ExtractedReport] = None,
    config: Optional[ScheduleUpdateConfig] = None,
) -> UpdateResult:
    """Convenience function for single-call updates.

    Creates a default ScheduleUpdater and processes the update.
    """
    updater = ScheduleUpdater(config=config)
    return updater.update_schedule(decision, extracted_report)