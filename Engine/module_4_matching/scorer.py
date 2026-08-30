"""
module_4_matching/scorer.py — Combines individual signals into MatchingScores.

RESPONSIBILITY:
    - Compute the (optional) discipline signal.
    - Renormalize configured weights over whichever signals were actually
      computable for this (report, candidate) pair (same pattern as
      Module 3's retrieval scorer, applied to Module 4's five signals).
    - Apply the contradiction penalty on top of the renormalized weighted
      sum, rather than folding contradictions into the weights themselves,
      so "explicit mismatch" stays visible and explainable as its own field
      (MatchingScores.contradiction_penalty) instead of being silently
      absorbed into a lower equipment_score/location_score.
"""

from __future__ import annotations

from typing import List, Tuple

from shared.schemas import MatchingScores

from .activity_matcher import score_activity
from .config import MatchingConfig
from .equipment_matcher import SignalResult, score_equipment
from .location_matcher import score_location
from .semantic_matcher import score_semantic


def score_discipline(activity_type_value, candidate_discipline, discipline_map) -> SignalResult:
    report_type = activity_type_value.value if activity_type_value else None
    type_key = getattr(report_type, "value", report_type)
    candidate_discipline = (candidate_discipline or "").strip() or None

    if not type_key or type_key == "UNKNOWN" or not candidate_discipline:
        return SignalResult(0.0, False, False, [])

    expected = discipline_map.get(str(type_key))
    if expected is None:
        return SignalResult(0.0, False, False, [])

    if expected.strip().lower() == candidate_discipline.strip().lower():
        return SignalResult(1.0, True, False, [f"Discipline consistent: {type_key} -> {expected}"])

    return SignalResult(
        0.3,
        True,
        False,
        [f"Discipline mismatch (soft signal): expected {expected} for {type_key}, candidate is {candidate_discipline}"],
    )


def combine_signals(
    semantic: SignalResult,
    equipment: SignalResult,
    activity: SignalResult,
    location: SignalResult,
    discipline: SignalResult,
    date: SignalResult,
    config: MatchingConfig,
) -> Tuple[MatchingScores, List[str]]:
    """Renormalizes config.weights over computable signals, applies the
    contradiction penalty, and returns the explainable MatchingScores plus
    a flat, de-duplicated explanation list.

    `date` (date_plausibility) is a soft tie-breaking signal, not a veto:
    a confident early-side date contradiction contributes to the same
    contradiction_penalty as equipment/location mismatches, but a
    late/slipped date never does (schedule slippage is normal)."""

    weight_map = config.weights.as_dict()
    signal_map = {
        "semantic_score": semantic,
        "equipment_score": equipment,
        "activity_score": activity,
        "location_score": location,
        "discipline_score": discipline,
        "date_score": date,
    }

    computable = {name: sig for name, sig in signal_map.items() if sig.computable}
    weight_sum = sum(weight_map[name] for name in computable) or 1.0
    raw_weighted = sum(weight_map[name] * sig.score for name, sig in computable.items())
    base_score = raw_weighted / weight_sum if computable else 0.0

    contradictions = [sig for sig in (equipment, location, date) if sig.contradiction]
    contradiction_penalty = min(
        config.max_contradiction_penalty,
        len(contradictions) * config.contradiction_penalty_per_signal,
    )

    final_score = base_score * (1.0 - contradiction_penalty)
    final_score = max(0.0, min(1.0, round(final_score, 4)))

    explanation: List[str] = []
    for sig in (equipment, location, activity, semantic, discipline, date):
        explanation.extend(sig.explanation)
    if contradiction_penalty > 0:
        explanation.append(
            f"Contradiction penalty applied: -{contradiction_penalty:.2f} to combined score"
        )

    scores = MatchingScores(
        semantic_score=round(semantic.score, 4),
        equipment_score=round(equipment.score, 4),
        location_score=round(location.score, 4),
        activity_score=round(activity.score, 4),
        discipline_score=round(discipline.score, 4) if discipline.computable else None,
        date_score=round(date.score, 4) if date.computable else None,
        contradiction_penalty=round(contradiction_penalty, 4),
        final_score=final_score,
    )
    return scores, explanation