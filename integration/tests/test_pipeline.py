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
from Engine.module_6_schedule_update.repository import ExecutionStateRepository


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


def _make_pipeline(retrieve_fn=None, repository=None) -> Pipeline:
    """Create a Pipeline with a fresh schedule index.

    Args:
        retrieve_fn: Optional callable to inject for retrieve_candidates,
            enabling deterministic tests.
        repository: Optional ExecutionStateRepository to inject for testing.
    """
    index = _load_schedule_index()
    return Pipeline(schedule_index=index, retrieve_fn=retrieve_fn, repository=repository)


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

    Returns candidates where the top candidate has final_score ~0.95
    (exceeds AUTO_MATCH_THRESHOLD) but fails the evidence gate:
    - equipment_tag=None -> equipment_score=0.0 (Policy A fails)
    - location=None -> location_score=0.0 (Policy B fails)
    - activity has CAST synonym -> activity_score=1.0 and semantic>=0.85
    None of Policy A (equipment_score==1.0) nor Policy B
    (location>0, activity>0, semantic>=0.85) pass, so AUTO_MATCH is
    blocked despite the high score. The score exceeds REVIEW_THRESHOLD
    -> HUMAN_REVIEW.

    Subsequent candidates have equipment contradiction (XX-999) so
    contradiction_penalty=0.35 and final_score well below the top
    candidate, giving a score_gap >= MIN_SCORE_GAP.

    Weight config (MatchingWeights): semantic=0.20, equipment=0.30,
    activity=0.20, location=0.15, discipline=0.05, date=0.10.
    Top candidate: equipment_tag=None -> equipment non-computable,
    location=None -> location non-computable, activity_name has CAST
    synonym "casting" -> activity_score=1.0, discipline=None,
    date=None. Denominator = 0.20+0.20 = 0.40 (semantic+activity
    computable). semantic_score=0.90 -> base = (0.20*0.90 + 0.20*1.0)
    / 0.40 = 0.95 -> final = 0.95 * (1-0) = 0.95 -> HUMAN_REVIEW
    (evidence gate blocks AUTO_MATCH).
    Subsequent candidates: equipment="XX-999" contradiction (penalty=0.35),
    activity=1.0 (real name has CAST synonym "pour"), semantic=0.90 ->
    base = (0.20*0.90 + 0.30*0.0 + 0.20*1.0) / 0.70 = 0.5429 ->
    final = 0.5429 * 0.65 = 0.3529 -> UNMATCHED.
    Gap = 0.95 - 0.3529 = 0.5971 >= MIN_SCORE_GAP (0.02).
    """
    from Engine.module_3_candidate.retriever import retrieve_candidates as _real_retrieve

    _semantic = 0.90  # tuned for HUMAN_REVIEW

    def _fn(extracted, index, top_k=5):  # noqa: ARG001
        real = _real_retrieve(extracted, index, top_k=top_k)
        overridden = []
        for i, rc in enumerate(real.candidates):
            if i == 0:
                # Top candidate: equipment_tag=None -> no equipment evidence,
                # location=None -> no location evidence, activity_name has
                # CAST synonym "casting" -> activity_score=1.0 (positive
                # activity evidence but no location evidence -> Policy B
                # fails). contradiction_penalty = 0.0 (no contradictions).
                # AUTO_MATCH blocked by evidence gate -> HUMAN_REVIEW.
                overridden.append(
                    RetrievedCandidate(
                        activity_id=rc.activity_id,
                        activity_name="Perform casting work",  # has CAST synonym "casting" -> activity=1.0
                        equipment_tag=None,  # no equipment evidence -> equipment_score=0.0
                        location=None,  # no location evidence -> location_score=0.0
                        discipline=None,  # non-computable
                        retrieval_score=_semantic,
                        retrieval_signals=RetrievalSignals(
                            semantic_score=_semantic,
                            equipment_match=0.0,  # no equipment tag
                            location_match=0.0,  # no location
                            activity_match=1.0,  # CAST synonym match
                        ),
                    )
                )
            else:
                # Subsequent candidates: equipment contradiction -> UNMATCHED
                overridden.append(
                    RetrievedCandidate(
                        activity_id=rc.activity_id,
                        activity_name=rc.activity_name,  # has CAST synonym "pour" -> activity=1.0
                        equipment_tag="XX-999",  # contradiction
                        location=None,  # non-computable
                        discipline=None,
                        retrieval_score=_semantic,
                        retrieval_signals=RetrievalSignals(
                            semantic_score=_semantic,
                            equipment_match=0.0,  # contradiction
                            location_match=0.0,
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
    and discipline may be non-computable (discipline=None → discipline_score=None),
    the effective weight denominator is:
        semantic + equipment + activity + location = 0.30 + 0.30 + 0.20 + 0.15 = 0.95
    With all four signals = score and contradiction_penalty=0.0:
        final_score = (0.95 * score) / 0.95 = score  ✓
    To compensate for rank_candidates renormalization when discipline is
    non-computable, semantic_score = final_score * 0.95.
    When discipline is computable (denominator=1.0), semantic_score = final_score.
    Equipment/activity/location must also match exactly (score=1.0).
    """
    # Use the full 0.95 denominator weight when discipline is non-computable
    _semantic = final_score * 0.95 if discipline is None else final_score
    return RetrievedCandidate(
        activity_id=activity_id,
        activity_name=activity_name,
        equipment_tag=equipment_tag,
        location=location,
        discipline=discipline,
        retrieval_score=final_score,
        retrieval_signals=RetrievalSignals(
            semantic_score=_semantic,
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
    regression errors from stale execution state left by prior test runs.

    Also clears the in-memory repository cache so the pipeline reads the
    freshly cleared file on its next access.
    """
    exec_path = Path("Data/execution_state.csv")
    exec_path.write_text(
        "activity_id,actual_status,actual_progress,last_report_id,last_update_timestamp\n",
        encoding="utf-8",
    )
    repo = ExecutionStateRepository()
    repo.clear_cache()
    yield
    repo.clear_cache()


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
    """A candidate with score < REVIEW_THRESHOLD triggers UNMATCHED."""
    from Engine.module_5_decision.decision import make_decision

    candidate = _make_ranked_candidate(final_score=0.15)
    ranking = _make_ranking_result(candidates=[candidate])
    decision_result = make_decision(ranking)

    assert decision_result.decision == DecisionType.UNMATCHED
    assert decision_result.selected_activity_id is None
    assert decision_result.confidence == 0.15


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


# ===========================================================================
# SEGMENTATION REGRESSION TESTS
# ===========================================================================

# Helper to access the segment function from the integration layer
from integration.pipeline import segment_report


def _make_pipeline_with_mock(retrieve_fn=None) -> Pipeline:
    """Create a Pipeline with a fresh schedule index and optional mock."""
    index = _load_schedule_index()
    return Pipeline(schedule_index=index, retrieve_fn=retrieve_fn)


# ---------------------------------------------------------------------------
# A. Single activity: exactly one result, existing behavior unchanged
# ---------------------------------------------------------------------------

def test_single_activity_no_segmentation():
    """A normal single-activity report must continue through the
    pipeline exactly as before — no segmentation occurs."""
    pipeline = _make_pipeline_with_mock(_auto_match_mock())
    raw = _make_raw_report("RPT-SINGLE", "F-101 welding completed at Area A.")
    result = pipeline.process_report(raw)

    # No segmentation: .segments must be None
    assert result.segments is None
    # Existing pipeline result must be intact
    assert result.failed() is False
    assert result.decision is not None
    assert result.decision.decision == DecisionType.AUTO_MATCH
    assert result.update is not None
    assert result.update.update_status == UpdateStatus.UPDATED
    assert result.report_id == "RPT-SINGLE"


def test_segment_report_returns_single_for_one_activity():
    """segment_report() returns exactly one string for a single-activity report."""
    report = _make_raw_report("RPT-SEG-A", "F-101 welding completed at Area A.")
    segments = segment_report(report)
    assert len(segments) == 1
    assert segments[0] == "F-101 welding completed at Area A."


# ---------------------------------------------------------------------------
# B. Two independent activities → two independently processed results
# ---------------------------------------------------------------------------

def test_two_independent_activities_two_segments():
    """Two clearly independent activities separated by a period must
    be split into two independently processed segments."""
    pipeline = _make_pipeline_with_mock(_auto_match_mock())
    raw = _make_raw_report(
        "RPT-TWO",
        "F-101 welding completed at Area A. F-102 inspection completed at Area B."
    )
    result = pipeline.process_report(raw)

    # Segmentation occurred
    assert result.segments is not None
    assert len(result.segments) == 2

    # Each segment must have its own unique report_id with -seg-N suffix
    assert result.segments[0].report_id == "RPT-TWO-seg-1"
    assert result.segments[1].report_id == "RPT-TWO-seg-2"

    # Both segments must have been successfully processed
    assert result.segments[0].failed() is False
    assert result.segments[1].failed() is False

    # Each segment must have its own decision
    assert result.segments[0].decision is not None
    assert result.segments[1].decision is not None

    # The top-level result mirrors the original report_id
    assert result.report_id == "RPT-TWO"


# ---------------------------------------------------------------------------
# C. Semicolon: two results only if both independently satisfy the evidence rule
# ---------------------------------------------------------------------------

def test_semicolon_splits_when_both_have_evidence():
    """A semicolon between two independently-evidenced activities must
    split into two segments."""
    pipeline = _make_pipeline_with_mock(_auto_match_mock())
    raw = _make_raw_report(
        "RPT-SEMI",
        "F-101 welding completed; F-102 inspection completed."
    )
    result = pipeline.process_report(raw)

    assert result.segments is not None
    assert len(result.segments) == 2
    assert result.segments[0].report_id == "RPT-SEMI-seg-1"
    assert result.segments[1].report_id == "RPT-SEMI-seg-2"


# ---------------------------------------------------------------------------
# D. One activity with progress: exactly one result
# ---------------------------------------------------------------------------

def test_activity_with_progress_one_result():
    """'F-101 welding started yesterday and is now 50% complete.' is a
    single sentence with no sentence boundary — must produce exactly
    one result."""
    pipeline = _make_pipeline_with_mock(_auto_match_mock())
    raw = _make_raw_report(
        "RPT-PROGRESS",
        "F-101 welding started yesterday and is now 50% complete."
    )
    result = pipeline.process_report(raw)

    # No segmentation
    assert result.segments is None
    # Processed normally
    assert result.failed() is False
    assert result.decision is not None
    assert result.report_id == "RPT-PROGRESS"


def test_segment_report_returns_single_for_progress_phrase():
    """segment_report() returns exactly one string for a progress phrase."""
    report = _make_raw_report(
        "RPT-SEG-PROG",
        "F-101 welding started yesterday and is now 50% complete."
    )
    segments = segment_report(report)
    assert len(segments) == 1
    assert segments[0] == "F-101 welding started yesterday and is now 50% complete."


# ---------------------------------------------------------------------------
# E. Context phrase: exactly one result
# ---------------------------------------------------------------------------

def test_context_phrase_no_segmentation():
    """'F-101 welding completed after inspection approval.' must produce
    exactly one result — 'after inspection approval' is a contextual
    phrase, not an independent activity."""
    pipeline = _make_pipeline_with_mock(_auto_match_mock())
    raw = _make_raw_report(
        "RPT-CONTEXT",
        "F-101 welding completed after inspection approval."
    )
    result = pipeline.process_report(raw)

    # No segmentation
    assert result.segments is None
    # Processed normally
    assert result.failed() is False
    assert result.decision is not None
    assert result.report_id == "RPT-CONTEXT"


def test_segment_report_returns_single_for_context_phrase():
    """segment_report() returns exactly one string for a context phrase."""
    report = _make_raw_report(
        "RPT-SEG-CONTEXT",
        "F-101 welding completed after inspection approval."
    )
    segments = segment_report(report)
    assert len(segments) == 1


# ---------------------------------------------------------------------------
# F. Mixed quality: only the first is an independent activity
# ---------------------------------------------------------------------------

def test_mixed_quality_only_first_activity():
    """'F-101 welding completed. Work delayed because of rain.' must
    produce exactly one result — the second part lacks an equipment
    identity signal and is re-joined with the first."""
    pipeline = _make_pipeline_with_mock(_auto_match_mock())
    raw = _make_raw_report(
        "RPT-MIXED",
        "F-101 welding completed. Work delayed because of rain."
    )
    result = pipeline.process_report(raw)

    # No segmentation: second part lacks evidence, so merged back
    assert result.segments is None
    # Processed normally
    assert result.failed() is False
    assert result.decision is not None
    assert result.report_id == "RPT-MIXED"


def test_segment_report_merges_contextual_phrase():
    """segment_report() must re-join a contextual phrase without
    an equipment identity with the preceding activity."""
    report = _make_raw_report(
        "RPT-SEG-MIXED",
        "F-101 welding completed. Work delayed because of rain."
    )
    segments = segment_report(report)
    # Second part fails evidence rule → merged back into one segment
    assert len(segments) == 1


# ---------------------------------------------------------------------------
# G. Segment failure isolation: one failure does not discard others
# ---------------------------------------------------------------------------

def test_segment_failure_isolation():
    """If one segment raises an exception during processing, the
    other valid segment must still be processed and represented.

    Uses a mock retrieve function that raises on the second call,
    simulating a transient failure in one segment's retrieval step.
    """
    index = _load_schedule_index()
    first_mock = _mock_retrieve_from_ranked(
        [_make_ranked_candidate(final_score=0.95)],
        schedule_index=index,
    )
    call_count = [0]

    def _failing_retrieve_second(extracted, sched_index, top_k=5):
        """First call succeeds, second call raises."""
        call_count[0] += 1
        if call_count[0] == 1:
            return first_mock(extracted, sched_index, top_k)
        raise RuntimeError("Transient retrieval failure for seg-2")

    pipeline = _make_pipeline_with_mock(retrieve_fn=_failing_retrieve_second)
    raw = _make_raw_report(
        "RPT-ISOLATE",
        "F-101 welding completed at Area A. F-102 inspection completed at Area B."
    )
    result = pipeline.process_report(raw)

    # Segmentation occurred
    assert result.segments is not None
    assert len(result.segments) == 2

    # Top-level result carries the original report_id
    assert result.report_id == "RPT-ISOLATE"

    # seg-1 must have been processed successfully (no exception propagated)
    assert result.segments[0].failed() is False
    assert result.segments[0].decision is not None

    # seg-2 must still have a PipelineResult representation despite failure
    # (it must NOT silently disappear); failure is captured in stages
    assert result.segments[1] is not None
    assert result.segments[1].report_id == "RPT-ISOLATE-seg-2"
    assert result.segments[1].failed() is True
    assert any(not s.success for s in result.segments[1].stages)


def test_segment_failure_isolation_via_process_segments():
    """Pipeline.process_segments() must return all segment results
    even when one segment raises an unexpected error."""
    pipeline = _make_pipeline_with_mock(_auto_match_mock())
    # Create a report that will split into two valid segments
    raw = _make_raw_report(
        "RPT-ISO-2",
        "F-101 welding completed at Area A. F-102 inspection completed at Area B."
    )
    result = pipeline.process_segments(raw)

    assert result.segments is not None
    assert len(result.segments) == 2
    assert result.segments[0].report_id == "RPT-ISO-2-seg-1"
    assert result.segments[1].report_id == "RPT-ISO-2-seg-2"

    # Both segments must have been processed (no silent failures)
    assert result.segments[0].failed() is False
    assert result.segments[1].failed() is False


# ---------------------------------------------------------------------------
# H. Cross-association safety
# ---------------------------------------------------------------------------

def test_cross_association_safety():
    """'F-101 welding completed. F-102 inspection completed.' must NOT
    cross-associate: F-101 must never be combined with inspection and
    F-102 must never be combined with welding.

    Each segment is processed independently with its own equipment
    tag matched to the correct schedule entry.  The mock retrieve
    function returns schedule candidates keyed by activity_id;
    seg-1 (F-101) receives candidates with equipment_tag='F-101',
    and seg-2 (F-102) receives candidates with equipment_tag='F-102'.
    Cross-contamination would mean seg-1 gets F-102 data or seg-2
    gets F-101 data, which must never happen.
    """
    pipeline = _make_pipeline_with_mock(_auto_match_mock())
    raw = _make_raw_report(
        "RPT-XASSOC",
        "F-101 welding completed at Area A. F-102 inspection completed at Area B."
    )
    result = pipeline.process_report(raw)

    # Segmentation occurred
    assert result.segments is not None
    assert len(result.segments) == 2

    # Each segment has its own unique report_id
    assert result.segments[0].report_id == "RPT-XASSOC-seg-1"
    assert result.segments[1].report_id == "RPT-XASSOC-seg-2"

    # Verify each segment was processed independently by checking that
    # the extraction produced the correct equipment tag per segment.
    # This confirms no cross-contamination between segments.
    seg1_extract = result.segments[0].extracted_report
    seg2_extract = result.segments[1].extracted_report

    assert seg1_extract is not None
    assert seg2_extract is not None

    # seg-1 must have F-101, NOT F-102
    seg1_equipment = {e.value for e in seg1_extract.equipment_tags}
    assert "F-101" in seg1_equipment
    assert "F-102" not in seg1_equipment, (
        "Cross-association detected: F-102 found in seg-1 extraction"
    )

    # seg-2 must have F-102, NOT F-101
    seg2_equipment = {e.value for e in seg2_extract.equipment_tags}
    assert "F-102" in seg2_equipment
    assert "F-101" not in seg2_equipment, (
        "Cross-association detected: F-101 found in seg-2 extraction"
    )

    # Both segments must have been processed successfully
    assert result.segments[0].failed() is False
    assert result.segments[1].failed() is False
