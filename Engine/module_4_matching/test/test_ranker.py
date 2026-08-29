"""
module_4_matching/test/test_ranker.py

Covers: exact match, wrong-equipment-but-similar-text, correct equipment
wrong activity, missing location, missing equipment, multiple close
candidates, empty candidate list, weight-config validation, report_id
mismatch, report_id preservation, tag identity matching.
"""

from __future__ import annotations

import pytest

from shared.constants import ActivityType
from shared.exceptions import MatchingError as SharedMatchingError
from shared.schemas import (
    ActivityTypeValue,
    CandidateRetrievalResult,
    EventTypeValue,
    ExtractedEntity,
    ExtractedNumericValue,
    ExtractedReport,
    RetrievalSignals,
    RetrievedCandidate,
)

from module_4_matching.config import MatchingConfig, MatchingWeights
from module_4_matching.exceptions import MatchingError
from module_4_matching.ranker import rank_candidates


def _report(
    report_id="RPT-0001",
    equipment=("SP-101",),
    locations=("Pump Area A",),
    activity_type=ActivityType.INSTALL,
) -> ExtractedReport:
    return ExtractedReport(
        report_id=report_id,
        normalized_text="SP-101 erection completed at Pump Area A",
        equipment_tags=[ExtractedEntity(value=v, confidence=0.9) for v in equipment],
        locations=[ExtractedEntity(value=v, confidence=0.9) for v in locations],
        activity_type=ActivityTypeValue(value=activity_type, confidence=0.9),
        event_type=EventTypeValue(),
        progress=ExtractedNumericValue(),
    )


def _candidate(
    activity_id="PIP-021",
    activity_name="Install piping spool SP-101",
    equipment_tag="SP-101",
    location="Pump Area A",
    discipline="Piping",
    retrieval_score=0.9,
    semantic_score=0.9,
) -> RetrievedCandidate:
    return RetrievedCandidate(
        activity_id=activity_id,
        activity_name=activity_name,
        equipment_tag=equipment_tag,
        location=location,
        discipline=discipline,
        wbs="1.2.3",
        retrieval_score=retrieval_score,
        retrieval_signals=RetrievalSignals(
            semantic_score=semantic_score,
            equipment_match=1.0,
            location_match=1.0,
            activity_match=1.0,
        ),
    )


def _candidates(report_id, *cands) -> CandidateRetrievalResult:
    return CandidateRetrievalResult(report_id=report_id, top_k=len(cands), candidates=list(cands))


def test_exact_match_scores_highest():
    report = _report()
    good = _candidate("PIP-021", "Install piping spool SP-101", "SP-101", "Pump Area A")
    bad = _candidate("PIP-054", "Install piping spool SP-101", "SP-101", "Pump Area B", semantic_score=0.4)
    result = rank_candidates(report, _candidates(report.report_id, good, bad))

    assert result.report_id == report.report_id
    assert result.ranked_candidates[0].activity_id == "PIP-021"
    assert result.ranked_candidates[0].rank == 1
    assert result.ranked_candidates[0].scores.final_score > result.ranked_candidates[1].scores.final_score


def test_wrong_equipment_but_similar_text_is_penalized():
    report = _report(equipment=("SP-101",))
    wrong_equipment = _candidate("PIP-099", "Install piping spool SP-999", "SP-999", "Pump Area A")
    result = rank_candidates(report, _candidates(report.report_id, wrong_equipment))

    ranked = result.ranked_candidates[0]
    assert ranked.scores.contradiction_penalty > 0.0
    assert any("mismatch" in e.lower() for e in ranked.explanation)


def test_correct_equipment_wrong_activity():
    report = _report(activity_type=ActivityType.WELD)
    candidate = _candidate("PIP-021", "Install piping spool SP-101", "SP-101", "Pump Area A")
    result = rank_candidates(report, _candidates(report.report_id, candidate))

    ranked = result.ranked_candidates[0]
    assert ranked.scores.activity_score < 0.5


def test_missing_location_is_not_computable_not_penalized():
    report = _report(locations=())
    candidate = _candidate(location="Pump Area A")
    result = rank_candidates(report, _candidates(report.report_id, candidate))

    ranked = result.ranked_candidates[0]
    assert ranked.scores.contradiction_penalty == 0.0
    assert ranked.scores.location_score == 0.0


def test_missing_equipment_is_not_computable_not_penalized():
    report = _report(equipment=())
    candidate = _candidate(equipment_tag="SP-101")
    result = rank_candidates(report, _candidates(report.report_id, candidate))

    ranked = result.ranked_candidates[0]
    assert ranked.scores.contradiction_penalty == 0.0


def test_multiple_close_candidates_are_deterministically_ordered():
    report = _report()
    a = _candidate("PIP-021", "Install piping spool SP-101", "SP-101", "Pump Area A")
    b = _candidate("PIP-022", "Install piping spool SP-101", "SP-101", "Pump Area A")
    result1 = rank_candidates(report, _candidates(report.report_id, a, b))
    result2 = rank_candidates(report, _candidates(report.report_id, b, a))

    ids1 = [c.activity_id for c in result1.ranked_candidates]
    ids2 = [c.activity_id for c in result2.ranked_candidates]
    assert ids1 == ids2 == ["PIP-021", "PIP-022"]


def test_empty_candidate_list_returns_empty_ranking_not_error():
    report = _report()
    result = rank_candidates(report, _candidates(report.report_id))
    assert result.ranked_candidates == []
    assert result.report_id == report.report_id


def test_report_id_mismatch_raises_matching_error():
    report = _report(report_id="RPT-0001")
    candidates = _candidates("RPT-9999", _candidate())
    with pytest.raises(MatchingError):
        rank_candidates(report, candidates)


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        MatchingWeights(
            semantic_weight=0.5,
            equipment_weight=0.5,
            activity_weight=0.5,
            location_weight=0.0,
            discipline_weight=0.0,
        ).validate()


def test_custom_weights_are_respected():
    report = _report()
    candidate = _candidate()
    heavy_semantic = MatchingConfig(
        weights=MatchingWeights(
            semantic_weight=1.0,
            equipment_weight=0.0,
            activity_weight=0.0,
            location_weight=0.0,
            discipline_weight=0.0,
        )
    )
    result = rank_candidates(report, _candidates(report.report_id, candidate), config=heavy_semantic)
    assert result.ranked_candidates[0].scores.final_score == pytest.approx(
        result.ranked_candidates[0].scores.semantic_score, abs=1e-4
    )


def test_report_id_preserved_through_ranking():
    report = _report(report_id="RPT-ZZZZ")
    result = rank_candidates(report, _candidates(report.report_id, _candidate()))
    assert result.report_id == "RPT-ZZZZ"


def test_matching_error_is_the_shared_contract_type():
    assert MatchingError is SharedMatchingError


def test_normalized_tag_forms_are_exact_matches():
    report = _report(equipment=("sp 101",))
    candidate = _candidate(equipment_tag="SP101")
    result = rank_candidates(report, _candidates(report.report_id, candidate))
    ranked = result.ranked_candidates[0]
    assert ranked.scores.equipment_score == 1.0
    assert ranked.scores.contradiction_penalty == 0.0


def test_substring_tag_is_a_contradiction():
    report = _report(equipment=("SP-101",))
    candidate = _candidate("MEC-004", "Install pump P-101", "P-101", "Pump Area A")
    result = rank_candidates(report, _candidates(report.report_id, candidate))
    ranked = result.ranked_candidates[0]
    assert ranked.scores.equipment_score == 0.0
    assert ranked.scores.contradiction_penalty > 0.0
    assert any("mismatch" in e.lower() for e in ranked.explanation)


def test_adjacent_area_is_a_location_contradiction():
    report = _report(locations=("Pump Area A",))
    candidate = _candidate(location="Pump Area B")
    result = rank_candidates(report, _candidates(report.report_id, candidate))
    ranked = result.ranked_candidates[0]
    assert ranked.scores.location_score == 0.0
    assert ranked.scores.contradiction_penalty > 0.0
