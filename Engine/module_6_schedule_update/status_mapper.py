"""
module_6_schedule_update/status_mapper.py — Event to Execution Status Mapping.

Translates extraction events (START, PROGRESS, FINISH) into actual execution
status and progress values. Pure, deterministic logic with no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shared.constants import EventType, ExecutionStatus
from shared.schemas import ExtractedReport


@dataclass(frozen=True)
class StatusMapping:
    """Result of mapping an event to execution status and progress."""
    actual_status: ExecutionStatus
    actual_progress: Optional[float]
    reason: str


class StatusMapper:
    """Maps EventType from extraction to ExecutionStatus and progress.

    Rules:
        START    → IN_PROGRESS, 0%
        PROGRESS → IN_PROGRESS, extracted progress (or preserved)
        FINISH   → COMPLETED, 100%
        UNKNOWN  → no change (preserve current state)
    """

    def map_event(
        self,
        event_type: EventType,
        extracted_progress: Optional[float],
        current_state: Optional[ExecutionStatus] = None,
        current_progress: Optional[float] = None,
    ) -> StatusMapping:
        """Map an event to the new execution status and progress.

        Args:
            event_type: The event type from extraction (START/PROGRESS/FINISH/UNKNOWN)
            extracted_progress: Progress value from extraction (0-100 or None)
            current_state: Current execution status (for preserving on UNKNOWN)
            current_progress: Current progress (for preserving on UNKNOWN/PROGRESS without value)

        Returns:
            StatusMapping with new status, progress, and human-readable reason.
        """
        if event_type == EventType.START:
            return StatusMapping(
                actual_status=ExecutionStatus.IN_PROGRESS,
                actual_progress=0.0,
                reason="Work started (START event) → IN_PROGRESS, 0%",
            )

        if event_type == EventType.PROGRESS:
            # Use extracted progress if available, otherwise preserve current
            progress = extracted_progress if extracted_progress is not None else current_progress
            return StatusMapping(
                actual_status=ExecutionStatus.IN_PROGRESS,
                actual_progress=progress,
                reason=f"Progress update (PROGRESS event) → IN_PROGRESS, {progress}%"
                if progress is not None
                else "Progress update (PROGRESS event, no percentage) → IN_PROGRESS, progress unchanged",
            )

        if event_type == EventType.FINISH:
            return StatusMapping(
                actual_status=ExecutionStatus.COMPLETED,
                actual_progress=100.0,
                reason="Work finished (FINISH event) → COMPLETED, 100%",
            )

        # EventType.UNKNOWN - preserve current state
        return StatusMapping(
            actual_status=current_state or ExecutionStatus.UNKNOWN,
            actual_progress=current_progress,
            reason="Unknown event type → state unchanged",
        )

    def map_from_extracted_report(
        self,
        report: ExtractedReport,
        current_state: Optional[ExecutionStatus] = None,
        current_progress: Optional[float] = None,
    ) -> StatusMapping:
        """Convenience method to map directly from an ExtractedReport."""
        return self.map_event(
            event_type=report.event_type.value,
            extracted_progress=report.progress.value,
            current_state=current_state,
            current_progress=current_progress,
        )


# Default instance for convenience
DEFAULT_STATUS_MAPPER = StatusMapper()