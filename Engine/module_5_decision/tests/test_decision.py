import pytest

from shared.schemas import RankingResult, RankedCandidate, MatchingScores
from shared.constants import DecisionType

from Engine.module_5_decision.decision import make_decision


def make_candidate(activity_id: str, final_score: float) -> RankedCandidate:
    return RankedCandidate(
        activity_id=activity_id,
        activity_name=f"Activity {activity_id}",
        rank=1,
        scores=MatchingScores(
            semantic_score=final_score,
            equipment_score=final_score,
            activity_score=final_score,
            discipline_score=final_score,
            location_score=final_score,
            temporal_score=final_score,
            contradiction_penalty=0.0,
            final_score=final_score,
        ),
        explanations=[],
    )


def test_auto_match():
    ranking = RankingResult(
        report_id="R1",
        ranked_candidates=[
            make_candidate("A1", 0.95),
            make_candidate("A2", 0.70),
        ],
    )

    result = make_decision(ranking)

    assert result.decision == DecisionType.AUTO_MATCH
    assert result.selected_activity_id == "A1"
    assert result.best_score == 0.95
    assert result.second_best_score == 0.70


def test_human_review_due_to_small_gap():
    ranking = RankingResult(
        report_id="R2",
        ranked_candidates=[
            make_candidate("A1", 0.90),
            make_candidate("A2", 0.86),
        ],
    )

    result = make_decision(ranking)

    assert result.decision == DecisionType.HUMAN_REVIEW
    assert result.selected_activity_id == "A1"


def test_human_review_due_to_medium_score():
    ranking = RankingResult(
        report_id="R3",
        ranked_candidates=[
            make_candidate("A1", 0.72),
            make_candidate("A2", 0.40),
        ],
    )

    result = make_decision(ranking)

    assert result.decision == DecisionType.HUMAN_REVIEW


def test_unmatched_low_score():
    ranking = RankingResult(
        report_id="R4",
        ranked_candidates=[
            make_candidate("A1", 0.45),
            make_candidate("A2", 0.30),
        ],
    )

    result = make_decision(ranking)

    assert result.decision == DecisionType.UNMATCHED
    assert result.selected_activity_id is None


def test_unmatched_no_candidates():
    ranking = RankingResult(
        report_id="R5",
        ranked_candidates=[],
    )

    result = make_decision(ranking)

    assert result.decision == DecisionType.UNMATCHED
    assert result.selected_activity_id is None
    assert result.confidence == 0.0


def test_single_strong_candidate_auto_match():
    ranking = RankingResult(
        report_id="R6",
        ranked_candidates=[
            make_candidate("A1", 0.92),
        ],
    )

    result = make_decision(ranking)

    assert result.decision == DecisionType.AUTO_MATCH
    assert result.selected_activity_id == "A1"
    assert result.second_best_score is None
    assert result.score_gap is None