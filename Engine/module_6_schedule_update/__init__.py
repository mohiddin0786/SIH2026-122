"""
module_6_schedule_update — Module 6: Schedule Update Engine.

Converts Decision Engine decisions into actual execution state updates
for schedule activities.

Pipeline position:
    Decision Engine (Module 5)
          ↓
    Schedule Update Engine (Module 6) ← THIS MODULE
          ↓
    Customer-facing result / UI

Main Interface:
    update_schedule(decision, extracted_report) -> UpdateResult

Key Types (from shared.schemas):
    DecisionResult     - Module 5 output (AUTO_MATCH/HUMAN_REVIEW/UNMATCHED)
    ExtractedReport    - Module 2 output (contains event_type, progress)
    ExecutionState     - Actual execution state (separate from baseline)
    UpdateResult       - Module 6 output (UPDATED/PENDING_REVIEW/NO_UPDATE)

Key Enums (from shared.constants):
    DecisionType       - AUTO_MATCH, HUMAN_REVIEW, UNMATCHED
    EventType          - START, PROGRESS, FINISH, UNKNOWN
    ExecutionStatus    - NOT_STARTED, IN_PROGRESS, COMPLETED, UNKNOWN
    UpdateStatus       - UPDATED, PENDING_REVIEW, NO_UPDATE
"""

from .config import ScheduleUpdateConfig, DEFAULT_CONFIG, load_config_from_dict
from .repository import ExecutionStateRepository, ExecutionStateRecord
from .status_mapper import StatusMapper, StatusMapping, DEFAULT_STATUS_MAPPER
from .updater import ScheduleUpdater, update_schedule

__all__ = [
    # Config
    "ScheduleUpdateConfig",
    "DEFAULT_CONFIG",
    "load_config_from_dict",
    # Repository
    "ExecutionStateRepository",
    "ExecutionStateRecord",
    # Status Mapper
    "StatusMapper",
    "StatusMapping",
    "DEFAULT_STATUS_MAPPER",
    # Updater
    "ScheduleUpdater",
    "update_schedule",
]

__version__ = "1.0.0"