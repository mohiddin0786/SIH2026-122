"""
module_4_matching/activity_matcher.py — Activity-type scoring signal.

Compares the extracted (categorical) activity_type against the candidate's
free-text activity_name, via a configurable synonym table (e.g. INSTALL ->
"erection", "installation", ...). Not a contradiction-detecting signal in
the same sense as equipment/location: a schedule activity_name simply not
containing a synonym is treated as "no match", not as a confident
contradiction (activity_name text is much noisier/freer than a tag or a
location field).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from rapidfuzz import fuzz

from .equipment_matcher import SignalResult


def score_activity(
    activity_type_value,
    candidate_activity_name: str,
    activity_synonyms: Dict[str, List[str]],
    fuzzy_match_floor: int,
) -> SignalResult:
    report_type = activity_type_value.value if activity_type_value else None
    # ActivityType enum members expose .value (e.g. "INSTALL"); tolerate a
    # plain string too so this stays testable without importing the enum.
    type_key = getattr(report_type, "value", report_type)

    candidate_name = (candidate_activity_name or "").strip()

    if not type_key or type_key == "UNKNOWN":
        return SignalResult(0.0, False, False, [])
    if not candidate_name:
        return SignalResult(0.0, False, False, [f"Report activity type {type_key} extracted but candidate has no activity_name"])

    synonyms = activity_synonyms.get(str(type_key), [])
    if not synonyms:
        return SignalResult(0.0, False, False, [f"No configured synonyms for activity type {type_key}"])

    name_lower = candidate_name.lower()
    best_score = 0.0
    best_synonym = None
    for syn in synonyms:
        syn_lower = syn.lower()
        if syn_lower in name_lower:
            best_score = 1.0
            best_synonym = syn
            break
        raw = fuzz.partial_ratio(syn_lower, name_lower)
        if raw >= fuzzy_match_floor:
            score = round(raw / 100.0, 4)
            if score > best_score:
                best_score = score
                best_synonym = syn

    if best_synonym is None:
        return SignalResult(
            0.0,
            True,
            False,
            [f"Activity type {type_key} has no matching term in candidate activity_name '{candidate_name}'"],
        )

    if best_score >= 0.999:
        return SignalResult(1.0, True, False, [f"Activity synonym match: {type_key} -> '{best_synonym}'"])

    return SignalResult(
        best_score,
        True,
        False,
        [f"Partial activity synonym match: {type_key} ~ '{best_synonym}' in '{candidate_name}' (similarity={best_score:.2f})"],
    )