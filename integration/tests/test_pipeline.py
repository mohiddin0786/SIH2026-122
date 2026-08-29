"""
Integration tests for the SIH2K26 end-to-end pipeline.

Covers all required scenarios using the actual dataset where possible,
with controlled synthetic inputs for decision-boundary cases.
"""

from __future__ import annotations

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
from shared.schemas import (
    RawReportInput,
    ExtractedEntity,
    ExtractedNumericValue,
    ActivityTypeValue,
    EventTypeValue,
    MatchingScores,
    RankedCandidate,
    RankingResult,
    CandidateRetrievalResult,
    RetrievedCandidate,
    RetrievalSignals,
    ExtractedReport,
)
from integration.pipeline import Pipeline, process_report, process_batch, _load_schedule_index


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_report(
    report_id: str = "RPT-0001",
    raw_text: str = "Excavate work for F 101 10% complete at PA-A.",
) -> RawReportInput:
    return RawReportInput(report_id=report_id, raw_text=raw_text)


def _make_ranked_candidate(
    activity_id: str = "CIV-001",
    activity_name: str = "Excavate foundation F-101",
    final_score: float = 0.95,
) -> RankedCandidate:
    return RankedCandidate(
        rank=1,
        activity_id=activity_id,
        activity_name=activity_name,
        scores=MatchingScores(
            semantic_score=final_score,
            equipment_score=final_score,
            location_score=final_score,
            activity_score=final_score,
            discipline_score=1.0,
            contradiction_penalty=0.0,
            final_score=final_score,
        ),
        explanation=[f"Score: {final_score}"],
    )


def _make_ranking_result(
    report_id: str = "RPT-0001",
    candidates: list[RankedCandidate] | None = None,
) -> RankingResult:
    if candidates is None:
        candidates = [_make_ranked_candidate()]
    return RankingResult(report_id=report_id, ranked_candidates=candidates)


def _make_pipeline(retrieve_fn=None) -> Pipeline:
    """Create a Pipeline with a fresh schedule index.

    Args:
        retrieve_fn: Optional callable to inject for retrieve_candidates,
            enabling deterministic tests.
    """
    index = _load_schedule_index()
    return Pipeline(schedule_index=index, retrieve_fn=retrieve_fn)


def _make_candidate_retrieved(
    activity_id: str = "CIV-001",
    activity_name: str = "Excavate foundation F-101",
    final_score: float = 0.95,
    equipment_tag: str = "F-101",
    location: str = "Pump Area A",
    discipline: str = "Civil",
) -> RetrievedCandidate:
    return RetrievedCandidate(
        activity_id=activity_id,
        activity_name=activity_name,
        equipment_tag=equipment_tag,
        location=location,
        discipline=discipline,
        retrieval_score=final_score,
        retrieval_signals=RetrievalSignals(
            semantic_score=final_score,
            equipment_match=1.0,
            location_match=1.0,
            activity_match=1.0,
        ),
    )


def _mock_retrieve_from_ranked(
    ranked_candidates: list[RankedCandidate],
    schedule_index=None,
) -> callable:
    """Return a mock retrieve function that uses real candidates from the
    schedule index (matching the report's equipment/activity) and overrides
    all signals to produce deterministic, well-separated scores.

    The first candidate gets all-match signals (semantic = final_score) so
    rank_candidates produces a final_score well above AUTO_MATCH_THRESHOLD.
    Subsequent candidates get equipment_tag="XX-999" so equipment_score=0.0
    AND contradiction=True (penalty=0.35), creating a large score gap
    (>= 0.10) to satisfy Module 5's MIN_SCORE_GAP.

    This ensures mock candidates have correct metadata for the report while
    keeping scores deterministic for tests (bypassing TF-IDF semantic noise).
    """
    from Engine.module_3_candidate.retriever import retrieve_candidates as _real_retrieve

    desired_scores = {c.activity_id: c.scores.final_score for c in ranked_candidates}

    def _fn(extracted, index, top_k=5):  # noqa: ARG001
        real = _real_retrieve(extracted, index, top_k=top_k)
        overridden = []
        for i, rc in enumerate(real.candidates):
            score = desired_scores.get(rc.activity_id, 0.95)
            if i == 0:
                # Top candidate: all signals match → final_score ≈ 0.985
                overridden.append(
                    RetrievedCandidate(
                        activity_id=rc.activity_id,
                        activity_name=rc.activity_name,
                        equipment_tag=rc.equipment_tag,
                        location=rc.location,
                        discipline=None,  # non-computable → final_score = semantic
                        retrieval_score=score,
                        retrieval_signals=RetrievalSignals(
                            semantic_score=score,
                            equipment_match=1.0,
                            location_match=1.0,
                            activity_match=1.0,
                        ),
                    )
                )
            else:
                # Subsequent candidates: equipment mismatch with CONTRADICTION
                # equipment_tag="XX-999" triggers contradiction → equipment=0.0, penalty=0.35
                # Final score ≈ (0.30*score + 0.20*1.0 + 0.15*1.0) * (1 - 0.35)
                #             ≈ score * 0.75 * 0.65 = score * 0.4875 → below 0.60 (UNMATCHED)
                # The gap to the top candidate (≈ score - score*0.4875) satisfies MIN_SCORE_GAP.
                overridden.append(
                    RetrievedCandidate(
                        activity_id=rc.activity_id,
                        activity_name=rc.activity_name,
                        equipment_tag="XX-999",  # contradiction → equipment=0.0, penalty=0.35
                        location=rc.location,
                        discipline=None,  # non-computable
                        retrieval_score=score,
                        retrieval_signals=RetrievalSignals(
                            semantic_score=score,
                            equipment_match=0.0,  # contradiction
                            location_match=1.0,
                            activity_match=1.0,
                        ),
                    )
                )
        return CandidateRetrievalResult(
            report_id=extracted.report_id,
            top_k=len(overridden),
            candidates=overridden,
        )
    return _fn


def _make_human_review_mock(schedule_index) -> callable:
    """Create a mock retrieve function for HUMAN_REVIEW tests.

    Returns candidates where the top candidate has final_score=0.72
    (HUMAN_REVIEW range: 0.60 <= score < 0.85) and a gap >= 0.10
    to the second candidate (final ≈ 0.468).

    discipline=None makes the discipline signal non-computable, so only
    4 signals contribute (denominator=0.95), and the weights renormalize:
        final = semantic * (0.30+0.30+0.20+0.15) / 0.95 = semantic.
    Setting semantic=0.72 → final=0.72 → HUMAN_REVIEW ✓
    Gap to second candidate (0.468) = 0.252 >= 0.10 → satisfies MIN_SCORE_GAP ✓
    """
    from Engine.module_3_candidate.retriever import retrieve_candidates as _real_retrieve

    def _fn(extracted, index, top_k=5):  # noqa: ARG001
        real = _real_retrieve(extracted, index, top_k=top_k)
        overridden = []
        for i, rc in enumerate(real.candidates):
            if i == 0:
                # Top candidate: semantic=0.72, no contradiction → final=0.72 (HUMAN_REVIEW)
                overridden.append(
                    RetrievedCandidate(
                        activity_id=rc.activity_id,
                        activity_name=rc.activity_name,
                        equipment_tag=rc.equipment_tag,
                        location=rc.location,
                        discipline=None,  # non-computable → final = semantic
                        retrieval_score=0.72,
                        retrieval_signals=RetrievalSignals(
                            semantic_score=0.72,
                            equipment_match=1.0,
                            location_match=1.0,
                            activity_match=1.0,
                        ),
                    )
                )
            else:
                # Subsequent candidates: equipment mismatch with CONTRADICTION
                # → final ≈ 0.468 (below 0.60), large gap to top candidate
                overridden.append(
                    RetrievedCandidate(
                        activity_id=rc.activity_id,
                        activity_name=rc.activity_name,
                        equipment_tag="XX-999",  # contradiction
                        location=rc.location,
                        discipline=None,  # non-computable
                        retrieval_score=0.72,
                        retrieval_signals=RetrievalSignals(
                            semantic_score=0.72,
                            equipment_match=0.0,  # contradiction
                            location_match=1.0,
                            activity_match=1.0,
                        ),
                    )
                )
        return CandidateRetrievalResult(
            report_id=extracted.report_id,
            top_k=len(overridden),
            candidates=overridden,
        )
    return _fn


def _mock_retrieve_with_scores(
    activity_id: str,
    activity_name: str,
    final_score: float,
    equipment_tag: str,
    location: str = "Pump Area A",
    discipline: str = "Civil",
) -> RetrievedCandidate:
    """Create a single RetrievedCandidate with all signals set to produce
    the exact final_score when rank_candidates recomputes them.

    Since rank_candidates recomputes scores via weighted combination,
    and the discipline signal is non-computable (discipline_score=None),
    the effective weight denominator is:
        semantic + equipment + activity + location = 0.30 + 0.30 + 0.20 + 0.15 = 0.95
    With all four signals = final_score and contradiction_penalty=0.0:
        final_score = (0.95 * score) / 0.95 = score  ✓
    But equipment/activity/location must also match exactly (score=1.0),
    and semantic_score must be set to the desired final_score directly
    (it is taken from retrieval_signals.semantic_score, not recomputed).
    """
    return RetrievedCandidate(
        activity_id=activity_id,
        activity_name=activity_name,
        equipment_tag=equipment_tag,
        location=location,
        discipline=discipline,
        retrieval_score=final_score,
        retrieval_signals=RetrievalSignals(
            semantic_score=final_score,
            equipment_match=1.0,
            location_match=1.0,
            activity_match=1.0,
        ),
    )


def _mock_retrieve(candidates: list[RetrievedCandidate]) -> callable:
    """Return a callable that ignores inputs and returns the given candidates,
    preserving the report_id from the ExtractedReport so rank_candidates'
    report_id consistency check passes."""
    def _fn(extracted, index, top_k=5):  # noqa: ARG001
        return CandidateRetrievalResult(
            report_id=extracted.report_id,
            top_k=len(candidates),
            candidates=candidates,
        )
    return _fn


# ---------------------------------------------------------------------------
# Pytest fixture: reset execution state before each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_execution_state():
    """Clear Data/execution_state.csv before each test to prevent state
    regression errors from stale execution state left by prior test runs."""
    exec_path = Path("Data/execution_state.csv")
    exec_path.write_text(
        "activity_id,actual_status,actual_progress,last_report_id,last_update_timestamp\n",
        encoding="utf-8",
    )
    yield


# ===========================================================================
# 1. Successful AUTO_MATCH (pipeline with injected high-scoring mock)
# ===========================================================================

def _auto_match_mock():
    """Create a mock retrieve function using real schedule candidates,
    overriding scores to 0.95 for deterministic AUTO_MATCH tests."""
    index = _load_schedule_index()
    return _mock_retrieve_from_ranked([_make_ranked_candidate(final_score=0.95)], schedule_index=index)


def test_auto_match_success():
    """Full pipeline with high-confidence candidates should produce AUTO_MATCH."""
    pipeline = _make_pipeline(retrieve_fn=_auto_match_mock())
    raw = _make_raw_report("RPT-0001", "Excavate work for F 101 10% complete at PA-A.")
    result = pipeline.process_report(raw)

    assert result.failed() is False
    assert result.decision is not None
    assert result.decision.decision == DecisionType.AUTO_MATCH
    assert result.decision.selected_activity_id == "CIV-001"
    assert result.update is not None
    assert result.update.update_status == UpdateStatus.UPDATED


# ===========================================================================
# 2. START → IN_PROGRESS, 0%
# ===========================================================================

def test_start_maps_to_in_progress_zero():
    """AUTO_MATCH + START event → IN_PROGRESS, 0%."""
    pipeline = _make_pipeline(retrieve_fn=_auto_match_mock())
    raw = _make_raw_report("RPT-0019", "Mechanical update: install of P 101 started at PA-A.")
    result = pipeline.process_report(raw)

    assert result.failed() is False
    assert result.decision.decision == DecisionType.AUTO_MATCH
    assert result.update is not None
    assert result.update.new_execution_state is not None
    assert result.update.new_execution_state.actual_status == ExecutionStatus.IN_PROGRESS
    assert result.update.new_execution_state.actual_progress == 0.0


# ===========================================================================
# 3. PROGRESS → correct percentage
# ===========================================================================

def test_progress_maps_to_correct_percentage():
    """AUTO_MATCH + PROGRESS event preserves the extracted percentage."""
    pipeline = _make_pipeline(retrieve_fn=_auto_match_mock())
    raw = _make_raw_report("RPT-0001", "Excavate work for F 101 10% complete at PA-A.")
    result = pipeline.process_report(raw)

    assert result.failed() is False
    assert result.decision.decision == DecisionType.AUTO_MATCH
    assert result.update is not None
    assert result.update.new_execution_state is not None
    assert result.update.new_execution_state.actual_progress == 10.0


# ===========================================================================
# 4. FINISH → COMPLETED / 100%
# ===========================================================================

def test_finish_maps_to_completed_100():
    """AUTO_MATCH + FINISH event → COMPLETED, 100%."""
    pipeline = _make_pipeline(retrieve_fn=_auto_match_mock())
    raw = _make_raw_report("RPT-0003", "F-101 foundation digging finished.")
    result = pipeline.process_report(raw)

    assert result.failed() is False
    assert result.decision.decision == DecisionType.AUTO_MATCH
    assert result.update is not None
    assert result.update.new_execution_state is not None
    assert result.update.new_execution_state.actual_status == ExecutionStatus.COMPLETED
    assert result.update.new_execution_state.actual_progress == 100.0


# ===========================================================================
# 5. HUMAN_REVIEW
# ===========================================================================

def test_human_review_decision():
    """A candidate with score in [0.60, 0.85) triggers HUMAN_REVIEW."""
    from Engine.module_5_decision.decision import make_decision

    candidate = _make_ranked_candidate(final_score=0.72)
    ranking = _make_ranking_result(candidates=[candidate])
    decision_result = make_decision(ranking)

    assert decision_result.decision == DecisionType.HUMAN_REVIEW
    assert decision_result.selected_activity_id == "CIV-001"


def test_human_review_produces_pending_review():
    """HUMAN_REVIEW decision → PENDING_REVIEW, no execution state update."""
    from Engine.module_5_decision.decision import make_decision
    from Engine.module_6_schedule_update.updater import ScheduleUpdater

    candidate = _make_ranked_candidate(final_score=0.72)
    ranking = _make_ranking_result(candidates=[candidate])
    decision_result = make_decision(ranking)
    assert decision_result.decision == DecisionType.HUMAN_REVIEW

    pipeline = _make_pipeline()
    updater = ScheduleUpdater(
        config=pipeline.config,
        schedule_master_df=pipeline._get_schedule_master_df(),
    )
    update_result = updater.update_schedule(decision_result, None)

    assert update_result.update_status == UpdateStatus.PENDING_REVIEW
    assert update_result.new_execution_state is None
    assert "human review" in update_result.update_reason.lower()


# ===========================================================================
# 6. UNMATCHED
# ===========================================================================

def test_unmatched_decision():
    """A candidate with score < 0.60 triggers UNMATCHED."""
    from Engine.module_5_decision.decision import make_decision

    candidate = _make_ranked_candidate(final_score=0.45)
    ranking = _make_ranking_result(candidates=[candidate])
    decision_result = make_decision(ranking)

    assert decision_result.decision == DecisionType.UNMATCHED
    assert decision_result.selected_activity_id is None
    assert decision_result.confidence == 0.45


def test_no_candidates_returns_unmatched():
    """If Module 3 returns no candidates, the decision is UNMATCHED."""
    from Engine.module_5_decision.decision import make_decision

    ranking = RankingResult(report_id="RPT-NO", ranked_candidates=[])
    decision_result = make_decision(ranking)
    assert decision_result.decision == DecisionType.UNMATCHED
    assert decision_result.selected_activity_id is None


# ===========================================================================
# 7. Invalid/unusable report
# ===========================================================================

def test_invalid_report_raises_validation_error():
    """A report that fails schema validation raises a clear error."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RawReportInput(report_id="", raw_text="some text")


def test_empty_raw_text_processed_gracefully():
    """Empty-ish raw text is processed without crashing the pipeline.

    The pipeline degrades gracefully: unknown activity type and no equipment
    tags are captured as flags rather than causing a crash.
    """
    from integration.pipeline import PipelineResult

    pipeline = _make_pipeline()
    raw = RawReportInput(report_id="RPT-EMPTY", raw_text="   ")
    result = pipeline.process_report(raw)
    assert isinstance(result, PipelineResult)
    # Should have been processed through all stages (even if some flags set)
    assert len(result.stages) >= 1


def test_report_with_no_candidates_returns_unmatched():
    """If Module 3 returns no candidates, the pipeline result shows no update."""
    pipeline = _make_pipeline(retrieve_fn=_mock_retrieve([]))
    raw = _make_raw_report("RPT-NO-CAND", "Some random text.")
    result = pipeline.process_report(raw)
    assert result.failed() is False
    assert result.decision is not None
    assert result.decision.decision == DecisionType.UNMATCHED
    assert result.decision.selected_activity_id is None
    assert result.update is None or result.update.update_status == UpdateStatus.NO_UPDATE


# ===========================================================================
# 8. Duplicate report
# ===========================================================================

def test_duplicate_report_idempotent():
    """Processing the same report twice is idempotent (second returns UPDATED)."""
    index = _load_schedule_index()
    retrieve_fn = _mock_retrieve_from_ranked([_make_ranked_candidate(final_score=0.95)], schedule_index=index)
    pipeline = _make_pipeline(retrieve_fn=retrieve_fn)
    raw = _make_raw_report("RPT-DUP", "Cast work for F 101 90% complete at PA-A.")

    result1 = pipeline.process_report(raw)
    assert result1.failed() is False
    assert result1.update is not None
    assert result1.update.update_status == UpdateStatus.UPDATED
    assert result1.update.new_execution_state is not None

    result2 = pipeline.process_report(raw)
    assert result2.failed() is False
    assert result2.update is not None
    assert result2.update.update_status == UpdateStatus.UPDATED
    assert "already processed" in result2.update.update_reason.lower()


# ===========================================================================
# 9. Baseline Schedule Master remains unchanged
# ===========================================================================

def test_baseline_schedule_master_unchanged():
    """Planned fields in the Schedule Master are never mutated by the pipeline."""
    schedule_master_path = "Data/schedule_master_v1.csv"
    df_before = pd.read_csv(schedule_master_path, dtype=str)
    baseline_row = df_before[df_before["activity_id"] == "CIV-001"].iloc[0]
    planned_start_before = baseline_row["planned_start"]
    planned_finish_before = baseline_row["planned_finish"]
    planned_duration_before = baseline_row["planned_duration_days"]
    baseline_status_before = baseline_row["baseline_status"]

    pipeline = _make_pipeline()
    raw = _make_raw_report("RPT-BASE", "Cast work for F 101 90% complete at PA-A.")
    pipeline.process_report(raw)

    df_after = pd.read_csv(schedule_master_path, dtype=str)
    baseline_row_after = df_after[df_after["activity_id"] == "CIV-001"].iloc[0]
    assert baseline_row_after["planned_start"] == planned_start_before
    assert baseline_row_after["planned_finish"] == planned_finish_before
    assert baseline_row_after["planned_duration_days"] == planned_duration_before
    assert baseline_row_after["baseline_status"] == baseline_status_before


# ===========================================================================
# 10. Customer-facing summary
# ===========================================================================

def test_to_summary_is_customer_facing():
    """PipelineResult.to_summary() returns clean, human-readable info."""
    pipeline = _make_pipeline()
    raw = _make_raw_report("RPT-SUMM", "Cast work for F 101 90% complete at PA-A.")
    result = pipeline.process_report(raw)

    summary = result.to_summary()
    assert "report_id" in summary
    assert "status" in summary
    assert result.decision is not None
    assert "decision" in summary
    assert result.update is not None
    assert "update_status" in summary
    # current_progress and current_status may or may not be present depending on decision
    # (they're only in summary when update.new_execution_state is not None)


# ===========================================================================
# 11. Process batch (multiple reports)
# ===========================================================================

def test_process_batch():
    """process_batch handles multiple reports without crashing on one failure."""
    pipeline = _make_pipeline()
    reports = [
        _make_raw_report("RPT-B1", "Cast work for F 101 90% complete at PA-A."),
        _make_raw_report("RPT-B2", "Installation work for P 101 started at PA-A."),
    ]
    results = pipeline.process_batch(reports)
    assert len(results) == 2
    for res in results:
        assert res.failed() is False
        assert res.decision is not None


# ===========================================================================
# 12. Pipeline isolates errors per-report
# ===========================================================================

def test_pipeline_error_isolation():
    """A failing report does not crash the batch; other reports still process."""
    pipeline = _make_pipeline()
    reports = [
        _make_raw_report("RPT-OK-1", "Cast work for F 101 90% complete at PA-A."),
        RawReportInput(report_id="RPT-OK-2", raw_text="some activity"),
    ]
    results = pipeline.process_batch(reports)
    assert len(results) == 2
    processed = [r for r in results if not r.failed()]
    assert len(processed) >= 1


# ===========================================================================
# 13. State lifecycle: START → PROGRESS → FINISH
# ===========================================================================

def test_full_state_lifecycle():
    """Test the full lifecycle: START → PROGRESS 30% → FINISH."""
    from Engine.module_5_decision.decision import make_decision
    from Engine.module_6_schedule_update.updater import ScheduleUpdater

    pipeline = _make_pipeline()
    updater = ScheduleUpdater(
        config=pipeline.config,
        schedule_master_df=pipeline._get_schedule_master_df(),
    )

    # Each step uses a UNIQUE report_id to avoid duplicate detection
    ranking = _make_ranking_result(candidates=[_make_ranked_candidate()])
    decision_result = make_decision(ranking)

    start_report = ExtractedReport(
        report_id="RPT-LIFE-START",
        normalized_text="Test",
        equipment_tags=[ExtractedEntity(value="F-101", confidence=0.9)],
        locations=[],
        activity_type=ActivityTypeValue(value=ActivityType.EXCAVATE, confidence=0.9),
        event_type=EventTypeValue(value=EventType.START, confidence=0.9),
        progress=ExtractedNumericValue(value=0.0, confidence=0.9),
    )
    r1 = updater.update_schedule(decision_result, start_report)
    assert r1.new_execution_state.actual_status == ExecutionStatus.IN_PROGRESS
    assert r1.new_execution_state.actual_progress == 0.0

    progress_report = ExtractedReport(
        report_id="RPT-LIFE-PROGRESS",
        normalized_text="Test",
        equipment_tags=[ExtractedEntity(value="F-101", confidence=0.9)],
        locations=[],
        activity_type=ActivityTypeValue(value=ActivityType.EXCAVATE, confidence=0.9),
        event_type=EventTypeValue(value=EventType.PROGRESS, confidence=0.9),
        progress=ExtractedNumericValue(value=30.0, confidence=0.9),
    )
    r2 = updater.update_schedule(decision_result, progress_report)
    assert r2.new_execution_state.actual_progress == 30.0

    finish_report = ExtractedReport(
        report_id="RPT-LIFE-FINISH",
        normalized_text="Test",
        equipment_tags=[ExtractedEntity(value="F-101", confidence=0.9)],
        locations=[],
        activity_type=ActivityTypeValue(value=ActivityType.EXCAVATE, confidence=0.9),
        event_type=EventTypeValue(value=EventType.FINISH, confidence=0.9),
        progress=ExtractedNumericValue(value=100.0, confidence=0.9),
    )
    r3 = updater.update_schedule(decision_result, finish_report)
    assert r3.new_execution_state.actual_status == ExecutionStatus.COMPLETED
    assert r3.new_execution_state.actual_progress == 100.0


# ===========================================================================
# 14. HUMAN_REVIEW → PENDING_REVIEW via pipeline (mocked retrieval)
# ===========================================================================

def test_human_review_via_pipeline():
    """Pipeline with a HUMAN_REVIEW-scoring mock returns PENDING_REVIEW."""
    index = _load_schedule_index()
    mock = _make_human_review_mock(index)
    pipeline = _make_pipeline(retrieve_fn=mock)
    raw = _make_raw_report("RPT-HR", "Cast work for F 101 72% complete at PA-A.")
    result = pipeline.process_report(raw)

    assert result.failed() is False
    assert result.decision.decision == DecisionType.HUMAN_REVIEW
    assert result.update is None or result.update.update_status == UpdateStatus.PENDING_REVIEW
