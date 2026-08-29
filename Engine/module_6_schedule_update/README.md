# Module 6: Schedule Update Engine

## Purpose

The Schedule Update Engine (Module 6) converts validated execution decisions from the Decision Engine (Module 5) into actual execution state updates for schedule activities. It maintains a separate execution state store that tracks **actual** progress, status, and timestamps — never modifying the baseline Schedule Master.

## Pipeline Position

```
Raw Report
    ↓
Normalization (Module 1)
    ↓
Extraction (Module 2)
    ↓
Candidate Retrieval (Module 3)
    ↓
Matching & Ranking (Module 4)
    ↓
Decision Engine (Module 5)
    ↓
Schedule Update Engine (Module 6)  ← THIS MODULE
    ↓
Customer-facing Result / UI
```

## Inputs

| Input | Type | Source |
|-------|------|--------|
| `decision` | `DecisionResult` | Module 5 (Decision Engine) |
| `extracted_report` | `ExtractedReport` (optional) | Module 2 (Extraction) |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `UpdateResult` | `UpdateResult` | Structured result with status, states, and reason |

## Decision Handling

### AUTO_MATCH
- **Action**: Updates execution state for the selected activity
- **Requirements**: `selected_activity_id` must be set and exist in Schedule Master
- **Returns**: `UpdateStatus.UPDATED` with `previous_execution_state` and `new_execution_state`
- **Idempotent**: Duplicate `report_id` for same activity returns current state without modification

### HUMAN_REVIEW
- **Action**: No automatic update
- **Returns**: `UpdateStatus.PENDING_REVIEW` with `activity_id` set to leading candidate (if any)
- **Reason**: Explains that human confirmation is required

### UNMATCHED
- **Action**: No update
- **Returns**: `UpdateStatus.NO_UPDATE` with `activity_id = None`
- **Reason**: Explains no activity could be confidently matched

## Event Handling

The engine maps extraction `EventType` to `ExecutionStatus` and progress:

| EventType | ExecutionStatus | Actual Progress | Notes |
|-----------|----------------|-----------------|-------|
| `START` | `IN_PROGRESS` | 0% | Work has begun |
| `PROGRESS` | `IN_PROGRESS` | Extracted % (0-100) | Uses extracted progress; preserves current if not provided |
| `FINISH` | `COMPLETED` | 100% | Work completed |
| `UNKNOWN` | Unchanged | Unchanged | No state change |

## Execution State

The `ExecutionState` model (from `shared.schemas`) tracks **actual** execution:

```python
activity_id: str              # Links to Schedule Master
actual_status: ExecutionStatus  # NOT_STARTED | IN_PROGRESS | COMPLETED | UNKNOWN
actual_progress: float | None   # 0-100 percentage
last_report_id: str | None      # Report that caused last update
last_update_timestamp: str      # ISO-8601 UTC timestamp
```

**Critical**: This is SEPARATE from baseline fields in Schedule Master:
- `planned_start` — NEVER modified
- `planned_finish` — NEVER modified
- `planned_duration_days` — NEVER modified
- `baseline_status` — NEVER modified

## Storage

### Execution State Store
- **Location**: `Data/execution_state.csv` (configurable)
- **Format**: CSV with columns: `activity_id, actual_status, actual_progress, last_report_id, last_update_timestamp`
- **Auto-created**: On first use if `auto_create_execution_store=True`
- **Isolation**: Completely separate from `schedule_master_v1.csv`, `raw_reports_v1.csv`, `ground_truth_v1.csv`

### Schedule Master
- **Location**: `Data/schedule_master_v1.csv` (read-only)
- **Purpose**: Baseline plan only — never modified by this module

## Baseline Protection

The Schedule Update Engine **never modifies** the Schedule Master. The baseline plan remains immutable:

```csv
activity_id,planned_start,planned_finish,planned_duration_days,baseline_status
CIV-001,2026-01-05,2026-01-07,3,Not Started
```

If CIV-001 actually finishes on 2026-01-08:
- Schedule Master: `planned_finish` stays `2026-01-07`
- Execution State: `actual_status=COMPLETED`, `actual_progress=100`, `last_update_timestamp=2026-01-08T...`

## Duplicate Report Handling

- Uses `last_report_id` in `ExecutionState` for idempotency
- If same `report_id` is processed again for the same `activity_id`:
  - Returns `UpdateStatus.UPDATED` with current state
  - No state modification
  - Reason: "Report {report_id} already processed for this activity (idempotent)"

## State Regression Protection

- **Default**: Prevents `COMPLETED` → `IN_PROGRESS` regression
- **Config**: `allow_state_regression=False` (default)
- **Behavior**: Older reports arriving after completion are rejected with `NO_UPDATE`
- **Reason**: "State regression blocked: COMPLETED → IN_PROGRESS. Report {report_id} would revert COMPLETED activity."

## Usage Example

```python
from shared.schemas import DecisionResult, ExtractedReport
from shared.constants import DecisionType, EventType
from module_6_schedule_update import update_schedule, ScheduleUpdateConfig

# Configure with custom paths (optional)
config = ScheduleUpdateConfig(
    schedule_master_path="Data/schedule_master_v1.csv",
    execution_state_path="Data/execution_state.csv",
)

# AUTO_MATCH + FINISH example (using real activity from Schedule Master)
decision = DecisionResult(
    report_id="RPT-0003",
    decision=DecisionType.AUTO_MATCH,
    selected_activity_id="CIV-001",  # Real activity from schedule_master_v1.csv
    confidence=0.96,
)

extracted = ExtractedReport(
    report_id="RPT-0003",
    normalized_text="F-101 foundation digging finished.",
    equipment_tags=[...],
    locations=[...],
    activity_type=ActivityTypeValue(value=ActivityType.EXCAVATE, confidence=0.9),
    event_type=EventTypeValue(value=EventType.FINISH, confidence=0.95),
    progress=ExtractedNumericValue(value=100.0, confidence=0.95),
)

result = update_schedule(decision, extracted, config)

# Result:
# UpdateResult(
#     report_id="RPT-0003",
#     update_status=UpdateStatus.UPDATED,
#     activity_id="CIV-001",
#     previous_execution_state=ExecutionState(...),
#     new_execution_state=ExecutionState(
#         activity_id="CIV-001",
#         actual_status=ExecutionStatus.COMPLETED,
#         actual_progress=100.0,
#         last_report_id="RPT-0003",
#         last_update_timestamp="2026-08-29T14:30:00Z"
#     ),
#     update_reason="AUTO_MATCH: Work finished (FINISH event) → COMPLETED, 100%. Confidence: 0.96"
# )
```

## Running Tests

```bash
# Run Module 6 tests
pytest Engine/module_6_schedule_update/tests/ -v

# Run all project tests
pytest -v
```

## Test Coverage

| Test | Description |
|------|-------------|
| `test_auto_match_start` | START → IN_PROGRESS, 0% |
| `test_auto_match_progress` | PROGRESS 50% → IN_PROGRESS, 50% |
| `test_auto_match_finish` | FINISH → COMPLETED, 100% |
| `test_human_review_no_update` | HUMAN_REVIEW → PENDING_REVIEW |
| `test_unmatched_no_update` | UNMATCHED → NO_UPDATE |
| `test_invalid_activity_id` | Non-existent activity handled safely |
| `test_invalid_progress_below_zero` | Progress < 0 rejected |
| `test_invalid_progress_above_100` | Progress > 100 rejected |
| `test_duplicate_report_idempotent` | Same report twice is safe |
| `test_completed_regression_blocked` | COMPLETED can't regress |
| `test_baseline_protection` | Schedule Master unchanged |
| `test_fresh_store_initialization` | Auto-creates execution store |
| `test_update_result_schema_validation` | Output conforms to schema |

## Configuration

```python
from module_6_schedule_update import ScheduleUpdateConfig

config = ScheduleUpdateConfig(
    schedule_master_path="Data/schedule_master_v1.csv",  # Baseline schedule
    execution_state_path="Data/execution_state.csv",      # Actual execution
    auto_create_execution_store=True,                      # Create if missing
    allow_state_regression=False,                          # Block COMPLETED→IN_PROGRESS
    timestamp_format="%Y-%m-%dT%H:%M:%SZ",                # ISO-8601 UTC
)
```

## Architecture

```
DecisionResult
      +
ExtractedReport
      ↓
ScheduleUpdater.update_schedule()
      ↓
  ┌───┴───┐
  │       │
  ▼       ▼
Validate  StatusMapper.map_event()
Decision    │
  │       ▼
  │   ExecutionState
  │       │
  │   Repository.save()
  │       │
  └───┬───┘
      ▼
  UpdateResult
```

## Limitations

1. **Single-writer**: CSV store not designed for concurrent writers
2. **Prototype storage**: CSV suitable for SIH demo; production would use a database
3. **No conflict resolution**: Multiple reports for same activity at same timestamp use last-write-wins
4. **Module 5 not yet implemented**: DecisionResult contract is defined but no producer exists yet
5. **No audit trail**: Only last report tracked; full history would require append-only store