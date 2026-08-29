"""
module_4_matching/ranker.py — MODULE 4: DETAILED MATCHING & RANKING.

RESPONSIBILITY:
    Given an ExtractedReport and the CandidateRetrievalResult from Module 3,
    compute an explainable, weighted score for every candidate and return
    them sorted by final_score descending. Does NOT decide AUTO_MATCH /
    HUMAN_REVIEW / UNMATCHED (Module 5's job), does NOT update the schedule,
    and never reads ground truth.

CORE FUNCTION:
    rank_candidates(report, candidates, config=None) -> RankingResult

Ties on final_score are broken deterministically by activity_id ascending,
matching Module 3's convention, so output is stable regardless of input
candidate order.
"""

from __future__ import annotations

import logging
from typing import Optional

from shared.exceptions import MatchingError
from shared.schemas import CandidateRetrievalResult, ExtractedReport, RankedCandidate, RankingResult

from .activity_matcher import score_activity
from .config import MatchingConfig
from .equipment_matcher import score_equipment
from .location_matcher import score_location
from .scorer import combine_signals, score_discipline
from .semantic_matcher import score_semantic

logger = logging.getLogger(__name__)


def rank_candidates(
    report: ExtractedReport,
    candidates: CandidateRetrievalResult,
    config: Optional[MatchingConfig] = None,
) -> RankingResult:
    """Scores and ranks every candidate in `candidates` against `report`.

    Raises MatchingError (report_id preserved) on structurally invalid
    input — e.g. report_id mismatch between the two inputs. An empty
    candidate list is not an error: it returns a RankingResult with an
    empty ranked_candidates list, for Module 5 to interpret as UNMATCHED-
    eligible.
    """
    if config is None:
        config = MatchingConfig()
    else:
        config.weights.validate()

    if report is None:
        raise MatchingError("report must not be None")
    if candidates is None:
        raise MatchingError("candidates must not be None", report_id=getattr(report, "report_id", None))
    if report.report_id != candidates.report_id:
        raise MatchingError(
            f"report_id mismatch between ExtractedReport ({report.report_id!r}) "
            f"and CandidateRetrievalResult ({candidates.report_id!r})",
            report_id=report.report_id,
        )

    if not candidates.candidates:
        logger.info("rank_candidates: no candidates to rank for report_id=%s", report.report_id)
        return RankingResult(report_id=report.report_id, ranked_candidates=[])

    scored = []
    for candidate in candidates.candidates:
        semantic = score_semantic(candidate.retrieval_signals)
        equipment = score_equipment(report.equipment_tags, candidate.equipment_tag, config.fuzzy_match_floor)
        activity = score_activity(
            report.activity_type, candidate.activity_name, config.activity_synonyms, config.fuzzy_match_floor
        )
        location = score_location(report.locations, candidate.location, config.fuzzy_match_floor)
        discipline = score_discipline(report.activity_type, candidate.discipline, config.discipline_map)

        scores, explanation = combine_signals(semantic, equipment, activity, location, discipline, config)
        scored.append((scores.final_score, candidate.activity_id, candidate, scores, explanation))

    # Sort by final_score descending; break ties deterministically by
    # activity_id ascending, not input order.
    scored.sort(key=lambda x: (-x[0], x[1]))

    ranked_candidates = []
    for rank, (final_score, activity_id, candidate, scores, explanation) in enumerate(scored, start=1):
        ranked_candidates.append(
            RankedCandidate(
                rank=rank,
                activity_id=candidate.activity_id,
                activity_name=candidate.activity_name,
                scores=scores,
                explanation=explanation,
            )
        )

    logger.info(
        "rank_candidates: report_id=%s ranked %d candidates (top final_score=%.4f)",
        report.report_id,
        len(ranked_candidates),
        ranked_candidates[0].scores.final_score if ranked_candidates else 0.0,
    )

    return RankingResult(report_id=report.report_id, ranked_candidates=ranked_candidates)