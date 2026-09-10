"""
Tests for the exact-equipment-match retrieval guarantee introduced in
retriever.py: when a report has an extracted equipment tag, ALL schedule
activities whose equipment_tag exactly matches it must appear in the
returned candidate set, even if there are more of them than top_k.

Tests are deliberately self-contained — they build a tiny in-memory
schedule with no dependency on schedule_master_v1.csv.
"""

from __future__ import annotations

import pandas as pd
import pytest

from Engine.module_3_candidate.retriever import (
    ScheduleIndex,
    build_schedule_index,
    retrieve_candidates,
)
from shared.constants import ActivityType, EventType
from shared.schemas import (
    ActivityTypeValue,
    EventTypeValue,
    ExtractedEntity,
    ExtractedNumericValue,
    ExtractedReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_schedule(rows: list[dict]) -> pd.DataFrame:
    """Construct a minimal schedule DataFrame from a list of row dicts."""
    required_defaults = {
        "project_id": "PRJ-001",
        "wbs": "1.0",
        "discipline": "PIP",
        "activity_description": "",
        "work_package": "WP-01",
        "predecessor_activity_id": "",
        "planned_start": "2026-01-01",
        "planned_finish": "2026-06-30",
        "planned_duration_days": "30",
        "baseline_status": "NOT_STARTED",
        "location": "",
    }
    full_rows = []
    for r in rows:
        full_row = {**required_defaults, **r}
        full_rows.append(full_row)
    return pd.DataFrame(full_rows)


def _make_report(
    report_id: str,
    text: str,
    equipment_tag: str | None = None,
    activity_type: str = "UNKNOWN",
) -> ExtractedReport:
    eq_tags = (
        [ExtractedEntity(value=equipment_tag, confidence=0.95)]
        if equipment_tag
        else []
    )
    return ExtractedReport(
        report_id=report_id,
        normalized_text=text,
        equipment_tags=eq_tags,
        locations=[],
        activity_type=ActivityTypeValue(
            value=ActivityType(activity_type),
            confidence=0.0 if activity_type == "UNKNOWN" else 0.9,
        ),
        event_type=EventTypeValue(value=EventType.UNKNOWN, confidence=0.0),
        progress=ExtractedNumericValue(value=None, confidence=0.0),
        extraction_flags=[],
    )


# ---------------------------------------------------------------------------
# Test 1: All exact-tag candidates are returned even when count > top_k
# ---------------------------------------------------------------------------

def test_all_exact_tag_candidates_included_beyond_top_k():
    """
    A schedule has 8 activities for tag SP-101, top_k=5.
    The retriever must return all 8 SP-101 activities regardless of top_k.
    """
    sp_rows = [
        {"activity_id": f"PIP-{i:03d}", "activity_name": f"Activity {i} SP-101", "equipment_tag": "SP-101"}
        for i in range(1, 9)  # 8 activities for SP-101
    ]
    # One unrelated activity
    sp_rows.append({"activity_id": "MEC-001", "activity_name": "Install pump P-101", "equipment_tag": "P-101"})

    sched_df = _make_schedule(sp_rows)
    index = build_schedule_index(sched_df)

    report = _make_report("RPT-TEST", "SP-101 work completed.", equipment_tag="SP-101")
    result = retrieve_candidates(report, index, top_k=5)

    returned_ids = {c.activity_id for c in result.candidates}
    sp_ids = {f"PIP-{i:03d}" for i in range(1, 9)}

    # All 8 SP-101 activities must be present
    assert sp_ids.issubset(returned_ids), (
        f"Missing SP-101 candidates: {sp_ids - returned_ids}"
    )
    # top_k field must equal actual candidate count
    assert result.top_k == len(result.candidates)


# ---------------------------------------------------------------------------
# Test 2: No duplication — each candidate appears exactly once
# ---------------------------------------------------------------------------

def test_no_duplicate_candidates_when_tag_expands_pool():
    """
    Candidates that already appear in the top_k window must not be
    duplicated when the tag-expansion pass runs over them again.
    """
    sp_rows = [
        {"activity_id": f"PIP-{i:03d}", "activity_name": f"Weld SP-101 step {i}", "equipment_tag": "SP-101"}
        for i in range(1, 7)  # 6 activities for SP-101
    ]
    sched_df = _make_schedule(sp_rows)
    index = build_schedule_index(sched_df)

    report = _make_report("RPT-DEDUP", "SP-101 work done.", equipment_tag="SP-101")
    result = retrieve_candidates(report, index, top_k=5)

    ids = [c.activity_id for c in result.candidates]
    assert len(ids) == len(set(ids)), f"Duplicate candidates found: {ids}"


# ---------------------------------------------------------------------------
# Test 3: Normal (≤ top_k tags) path is unchanged
# ---------------------------------------------------------------------------

def test_top_k_respected_when_tag_count_below_top_k():
    """
    When only 3 activities share the extracted tag and top_k=5, the returned
    pool should still contain exactly those 3 plus up to 2 others from the
    semantic top-5 — never bloating to the full schedule.
    """
    rows = [
        {"activity_id": "PIP-001", "activity_name": "Install SP-101", "equipment_tag": "SP-101"},
        {"activity_id": "PIP-002", "activity_name": "Weld SP-101", "equipment_tag": "SP-101"},
        {"activity_id": "PIP-003", "activity_name": "Hydrotest SP-101", "equipment_tag": "SP-101"},
        {"activity_id": "MEC-001", "activity_name": "Install pump P-101", "equipment_tag": "P-101"},
        {"activity_id": "MEC-002", "activity_name": "Align pump P-101", "equipment_tag": "P-101"},
        {"activity_id": "MEC-003", "activity_name": "Inspect pump P-101", "equipment_tag": "P-101"},
        {"activity_id": "MEC-004", "activity_name": "Erect motor M-101", "equipment_tag": "M-101"},
        {"activity_id": "MEC-005", "activity_name": "Connect motor M-101", "equipment_tag": "M-101"},
    ]
    sched_df = _make_schedule(rows)
    index = build_schedule_index(sched_df)

    report = _make_report("RPT-NORM", "SP-101 work completed.", equipment_tag="SP-101")
    result = retrieve_candidates(report, index, top_k=5)

    returned_ids = {c.activity_id for c in result.candidates}
    # All 3 SP-101 candidates must be present
    assert {"PIP-001", "PIP-002", "PIP-003"}.issubset(returned_ids)
    # Total must not exceed 5 (3 tag-matches + 2 semantic fillers) plus at
    # most the 3 tag-matches themselves = 5, so ≤ 5
    assert len(result.candidates) <= 5


# ---------------------------------------------------------------------------
# Test 4: No tag extracted → pure top_k behaviour, no expansion
# ---------------------------------------------------------------------------

def test_no_tag_report_respects_top_k_strictly():
    """
    When the report has no equipment tag, the tag-expansion pass is
    a no-op and exactly top_k candidates are returned (or fewer if the
    schedule is smaller than top_k).
    """
    rows = [
        {"activity_id": f"PIP-{i:03d}", "activity_name": f"Piping activity {i}", "equipment_tag": "SP-101"}
        for i in range(1, 9)
    ]
    sched_df = _make_schedule(rows)
    index = build_schedule_index(sched_df)

    # No equipment tag extracted
    report = _make_report("RPT-NOTAG", "Work completed.", equipment_tag=None)
    result = retrieve_candidates(report, index, top_k=5)

    assert len(result.candidates) == 5, (
        f"Expected exactly 5 candidates, got {len(result.candidates)}"
    )


# ---------------------------------------------------------------------------
# Test 5: Regression — Group 3 reports now include GT in candidate pool
#   Uses the real schedule and real pipeline, mirrors the actual bug.
# ---------------------------------------------------------------------------

def test_sp101_gt_in_candidate_pool_for_generic_reports():
    """
    Regression test for the Group 3 retrieval truncation bug.
    SP-101 has 10 activities in schedule_master_v1.csv. With top_k=5 only,
    the fit-up and inspect activities (PIP-016, PIP-049, PIP-051) were
    silently dropped. After the fix they must be present.
    """
    import pandas as pd
    from pathlib import Path

    schedule_df = pd.read_csv(
        Path(__file__).parents[3] / "Data/schedule_master_v1.csv"
    )
    index = build_schedule_index(schedule_df)

    cases = [
        ("RPT-0095", "SP-101 work completed.", "SP-101", "PIP-016"),
        ("RPT-0293", "SP101 work 25% complete.", "SP-101", "PIP-049"),
        ("RPT-0305", "sp-101 work started.", "SP-101", "PIP-051"),
    ]

    for report_id, text, tag, expected_gt_id in cases:
        report = _make_report(report_id, text, equipment_tag=tag)
        result = retrieve_candidates(report, index, top_k=5)
        returned_ids = {c.activity_id for c in result.candidates}
        assert expected_gt_id in returned_ids, (
            f"{report_id}: expected GT candidate {expected_gt_id} in pool, "
            f"but only got {sorted(returned_ids)}"
        )
