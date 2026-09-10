"""
module_4_matching/equipment_matcher.py — Equipment-tag scoring signal.

Equipment tags are identity keys (F-101 vs P-101 vs SP-101), not free text.
Scoring is exact after a light normalize (case, spaces, hyphen). Substring
fuzzy match is never used — it treats SP-101 as a perfect match for P-101.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

_TAG_BODY_RE = re.compile(r"^([A-Z]+)(\d{3,4})$")


@dataclass
class SignalResult:
    score: float  # always 0.0-1.0, meaningful even when not computable (0.0)
    computable: bool  # False => no evidence on one or both sides
    contradiction: bool  # True => confident, explicit mismatch
    explanation: List[str]


def normalize_equipment_tag(value: Optional[str]) -> Optional[str]:
    """Canonical tag form, e.g. 'sp 101' / 'SP101' / 'sp-101' -> 'SP-101'.

    Unknown shapes still get a stable compact uppercase form so equality is
    well-defined. Returns None for blank input.
    """
    if not value:
        return None
    compact = re.sub(r"[\s_\-]+", "", str(value).strip().upper())
    if not compact:
        return None
    match = _TAG_BODY_RE.fullmatch(compact)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return compact


def _best_report_value(entities) -> Optional[str]:
    if not entities:
        return None
    best = max(entities, key=lambda e: e.confidence)
    value = (best.value or "").strip()
    return value or None


def score_equipment(
    report_equipment_tags,
    candidate_equipment_tag: Optional[str],
    fuzzy_match_floor: int,
) -> SignalResult:
    # fuzzy_match_floor is part of the matcher signature used by ranker/config
    # but must not apply to tags — identity keys are exact after normalize.
    _ = fuzzy_match_floor

    candidate_value = (candidate_equipment_tag or "").strip() or None

    if not report_equipment_tags and not candidate_value:
        return SignalResult(0.0, False, False, [])
    if not report_equipment_tags:
        return SignalResult(0.0, False, False, ["Candidate has an equipment tag but report does not mention one"])
    if not candidate_value:
        best_report_value = _best_report_value(report_equipment_tags)
        return SignalResult(
            0.0,
            False,
            False,
            [f"Report mentions equipment {best_report_value} but candidate has no equipment tag on file"],
        )

    # Compare candidate against ALL normalized report tags — not just the highest-confidence one.
    candidate_tag = normalize_equipment_tag(candidate_value)
    report_tags_normalized = [
        normalize_equipment_tag(ent.value.strip())
        for ent in report_equipment_tags
    ]
    # Filter out None values from normalization failures.
    report_tags_normalized = [t for t in report_tags_normalized if t]

    if candidate_tag and any(report_tag == candidate_tag for report_tag in report_tags_normalized):
        matched_tag = candidate_tag
        return SignalResult(1.0, True, False, [f"Exact equipment tag match: {matched_tag}"])

    report_value = _best_report_value(report_equipment_tags)
    return SignalResult(
        0.0,
        True,
        True,
        [f"Equipment tag mismatch: report={report_value} candidate={candidate_value}"],
    )
