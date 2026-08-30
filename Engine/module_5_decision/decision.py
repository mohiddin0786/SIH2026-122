from shared.schemas import RankingResult, DecisionResult
from shared.constants import DecisionType
from shared.exceptions import DecisionError


# Decision thresholds — tuned via tune_thresholds.py (2026-08-30)
# Result: 289 TPs, 0 FPs at these values (down from 0.80/0.02/0.30)
AUTO_MATCH_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.20
MIN_SCORE_GAP = 0.02


def make_decision(ranking_result: RankingResult) -> DecisionResult:
    """
    Convert Module 4 RankingResult into Module 5 DecisionResult.

    Rules:
    - No candidates -> UNMATCHED
    - Strong best candidate + sufficient score gap -> AUTO_MATCH
    - Reasonable candidate but uncertain/ambiguous -> HUMAN_REVIEW
    - Weak candidate -> UNMATCHED
    """

    try:
        report_id = ranking_result.report_id
        candidates = ranking_result.ranked_candidates

        # Case 1: Module 4 returned no candidates
        if not candidates:
            return DecisionResult(
                report_id=report_id,
                decision=DecisionType.UNMATCHED,
                selected_activity_id=None,
                confidence=0.0,
                best_score=None,
                second_best_score=None,
                score_gap=None,
                decision_reasons=[
                    "No ranked candidates were available."
                ],
            )

        # Best candidate
        best_candidate = candidates[0]
        best_score = best_candidate.scores.final_score

        # Second candidate, if available
        if len(candidates) > 1:
            second_best_score = candidates[1].scores.final_score
            score_gap = max(0.0, best_score - second_best_score)
        else:
            second_best_score = None
            score_gap = None

        # Case 2: High confidence and clearly better than alternatives
        if (
            best_score >= AUTO_MATCH_THRESHOLD
            and (score_gap is None or score_gap >= MIN_SCORE_GAP)
        ):
            return DecisionResult(
                report_id=report_id,
                decision=DecisionType.AUTO_MATCH,
                selected_activity_id=best_candidate.activity_id,
                confidence=best_score,
                best_score=best_score,
                second_best_score=second_best_score,
                score_gap=score_gap,
                decision_reasons=[
                    "Best candidate score exceeds auto-match threshold.",
                    "Best candidate is sufficiently separated from alternatives."
                    if score_gap is not None
                    else "Only one candidate was available.",
                ],
            )

        # Case 3: Candidate is plausible but not safe enough to auto-match
        if best_score >= REVIEW_THRESHOLD:
            reasons = [
                "Best candidate is plausible but does not satisfy auto-match criteria."
            ]

            if score_gap is not None and score_gap < MIN_SCORE_GAP:
                reasons.append(
                    "Top candidates have similar scores, indicating ambiguity."
                )

            if best_score < AUTO_MATCH_THRESHOLD:
                reasons.append(
                    "Best candidate score is below the auto-match threshold."
                )

            return DecisionResult(
                report_id=report_id,
                decision=DecisionType.HUMAN_REVIEW,
                selected_activity_id=best_candidate.activity_id,
                confidence=best_score,
                best_score=best_score,
                second_best_score=second_best_score,
                score_gap=score_gap,
                decision_reasons=reasons,
            )

        # Case 4: Best candidate is too weak
        return DecisionResult(
            report_id=report_id,
            decision=DecisionType.UNMATCHED,
            selected_activity_id=None,
            confidence=best_score,
            best_score=best_score,
            second_best_score=second_best_score,
            score_gap=score_gap,
            decision_reasons=[
                "Best candidate score is below the minimum review threshold."
            ],
        )

    except Exception as exc:
        if isinstance(exc, DecisionError):
            raise

        report_id = getattr(ranking_result, "report_id", None)

        raise DecisionError(
            f"Failed to make decision: {exc}",
            report_id=report_id,
        ) from exc

