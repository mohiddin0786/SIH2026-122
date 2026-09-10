import pytest

from shared.schemas import RankingResult, RankedCandidate, MatchingScores
from shared.constants import DecisionType

from Engine.module_5_decision.decision import make_decision


def make_candidate(
    activity_id: str,
    final_score: float,
    semantic_score: float = None,
    equipment_score: float = None,
    location_score: float = None,
    activity_score: float = None,
    discipline_score: float = None,
    date_score: float = None,
    contradiction_penalty: float = 0.0,
) -> RankedCandidate:
    """Create a RankedCandidate with configurable per-signal scores.

    Unspecified scores default to final_score.
    """
    if semantic_score is None:
        semantic_score = final_score
    if equipment_score is None:
        equipment_score = final_score
    if location_score is None:
        location_score = final_score
    if activity_score is None:
        activity_score = final_score
    if discipline_score is None:
        discipline_score = final_score
    if date_score is None:
        date_score = final_score
    return RankedCandidate(
        activity_id=activity_id,
        activity_name=f"Activity {activity_id}",
        rank=1,
        scores=MatchingScores(
            semantic_score=semantic_score,
            equipment_score=equipment_score,
            location_score=location_score,
            activity_score=activity_score,
            discipline_score=discipline_score,
            date_score=date_score,
            contradiction_penalty=contradiction_penalty,
            final_score=final_score,
        ),
        explanation=[],
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
            make_candidate("A2", 0.89),
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
            make_candidate("A1", 0.15),
            make_candidate("A2", 0.10),
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


# ---------------------------------------------------------------------------
# Regression tests — evidence gate
# ---------------------------------------------------------------------------

def test_semantic_only_090_is_human_review():
    """Semantic score 0.90 alone (no equipment, location, or activity evidence)
    must NOT auto-match even though final_score > AUTO_MATCH_THRESHOLD."""
    ranking = RankingResult(
        report_id="R7",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                semantic_score=0.90, equipment_score=0.0,
                location_score=0.0, activity_score=0.0,
            ),
            make_candidate("A2", final_score=0.40),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.HUMAN_REVIEW


def test_semantic_only_076_is_human_review():
    """Semantic score 0.76 alone must NOT auto-match."""
    ranking = RankingResult(
        report_id="R8",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.76,
                semantic_score=0.76, equipment_score=0.0,
                location_score=0.0, activity_score=0.0,
            ),
            make_candidate("A2", final_score=0.40),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.HUMAN_REVIEW


def test_semantic_plus_activity_only_is_human_review():
    """Semantic + activity only (no equipment, no location) must NOT auto-match."""
    ranking = RankingResult(
        report_id="R9",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                semantic_score=0.90, equipment_score=0.0,
                location_score=0.0, activity_score=0.90,
            ),
            make_candidate("A2", final_score=0.40),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.HUMAN_REVIEW


def test_semantic_plus_location_only_is_human_review():
    """Semantic + location only (no activity) must NOT auto-match."""
    ranking = RankingResult(
        report_id="R10",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                semantic_score=0.90, equipment_score=0.0,
                location_score=0.90, activity_score=0.0,
            ),
            make_candidate("A2", final_score=0.40),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.HUMAN_REVIEW


def test_exact_equipment_auto_match():
    """Exact equipment match (equipment_score == 1.0) with sufficient
    score and gap should AUTO_MATCH."""
    ranking = RankingResult(
        report_id="R11",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                equipment_score=1.0, semantic_score=0.5,
                location_score=0.5, activity_score=0.5,
            ),
            make_candidate("A2", final_score=0.50),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.AUTO_MATCH
    assert result.selected_activity_id == "A1"


def test_location_activity_semantic_strong_auto_match():
    """Location > 0 + activity > 0 + semantic >= 0.85 with sufficient
    score and gap should AUTO_MATCH."""
    ranking = RankingResult(
        report_id="R12",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                semantic_score=0.90, equipment_score=0.0,
                location_score=0.80, activity_score=0.80,
            ),
            make_candidate("A2", final_score=0.50),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.AUTO_MATCH
    assert result.selected_activity_id == "A1"


def test_contradiction_blocks_auto_match():
    """Any contradiction_penalty > 0 must NOT auto-match even with high score."""
    ranking = RankingResult(
        report_id="R13",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.95,
                contradiction_penalty=0.35,
            ),
            make_candidate("A2", final_score=0.70),
        ],
    )
    result = make_decision(ranking)
    assert result.decision != DecisionType.AUTO_MATCH
    assert result.decision == DecisionType.HUMAN_REVIEW


def test_high_score_insufficient_gap_is_not_auto_match():
    """High score with score_gap < MIN_SCORE_GAP must NOT auto-match."""
    ranking = RankingResult(
        report_id="R14",
        ranked_candidates=[
            make_candidate("A1", 0.90),
            make_candidate("A2", 0.89),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.HUMAN_REVIEW


def test_below_review_threshold_is_unmatched():
    """Score below REVIEW_THRESHOLD must be UNMATCHED."""
    ranking = RankingResult(
        report_id="R15",
        ranked_candidates=[
            make_candidate("A1", 0.15),
            make_candidate("A2", 0.10),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.UNMATCHED
    assert result.selected_activity_id is None


# ---------------------------------------------------------------------------
# Regression tests — same-tag ambiguity guardrail
# ---------------------------------------------------------------------------

def test_same_tag_no_activity_signal_is_human_review():
    """When top two candidates share the same equipment tag AND
    neither carries an activity signal (activity_score == 0.0),
    the case is inherently ambiguous and must be routed to
    HUMAN_REVIEW, not AUTO_MATCH, even if the score exceeds
    AUTO_MATCH_THRESHOLD."""
    ranking = RankingResult(
        report_id="R16",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                equipment_score=1.0, activity_score=0.0,
                semantic_score=0.77,
            ),
            make_candidate(
                "A2", final_score=0.87,
                equipment_score=1.0, activity_score=0.0,
                semantic_score=0.39,
            ),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.HUMAN_REVIEW
    assert any(
        "activity" in r.lower() or "ambiguous" in r.lower()
        for r in result.decision_reasons
    )


def test_same_tag_with_activity_signal_allows_auto_match():
    """When top two candidates share the same equipment tag but
    at least one has an activity signal (activity_score > 0.0),
    the guardrail should NOT block AUTO_MATCH."""
    ranking = RankingResult(
        report_id="R17",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                equipment_score=1.0, activity_score=0.95,
                semantic_score=0.80,
            ),
            make_candidate(
                "A2", final_score=0.80,
                equipment_score=1.0, activity_score=0.0,
                semantic_score=0.40,
            ),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.AUTO_MATCH
    assert result.selected_activity_id == "A1"


def test_different_equipment_tags_not_affected_by_guardrail():
    """The guardrail should NOT affect reports where the top two
    candidates have DIFFERENT equipment tags."""
    ranking = RankingResult(
        report_id="R18",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                equipment_score=1.0, activity_score=0.0,
                semantic_score=0.80,
            ),
            make_candidate(
                "A2", final_score=0.85,
                equipment_score=0.0, activity_score=0.0,
                semantic_score=0.50,
            ),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.AUTO_MATCH
    assert result.selected_activity_id == "A1"


def test_single_candidate_not_affected_by_guardrail():
    """The guardrail should NOT affect reports with only one candidate."""
    ranking = RankingResult(
        report_id="R19",
        ranked_candidates=[
            make_candidate(
                "A1", final_score=0.90,
                equipment_score=1.0, activity_score=0.0,
                semantic_score=0.80,
            ),
        ],
    )
    result = make_decision(ranking)
    assert result.decision == DecisionType.AUTO_MATCH
    assert result.selected_activity_id == "A1"
