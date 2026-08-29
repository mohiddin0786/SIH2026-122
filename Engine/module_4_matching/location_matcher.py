"""
module_4_matching/location_matcher.py — Location scoring signal.

Locations are near-identity (Pump Area A vs Pump Area B). `partial_ratio`
treats those as ~95% similar, so we canonicalize aliases, require an exact
match when the area code differs, and only use full-string ratio for typos.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from rapidfuzz import fuzz

from .equipment_matcher import SignalResult, _best_report_value

_LOCATION_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^pa[\s-]*a$", re.IGNORECASE), "pump area a"),
    (re.compile(r"^pump(?:\s+area)?\s+a$", re.IGNORECASE), "pump area a"),
    (re.compile(r"^pa[\s-]*b$", re.IGNORECASE), "pump area b"),
    (re.compile(r"^pump(?:\s+area)?\s+b$", re.IGNORECASE), "pump area b"),
    (re.compile(r"^pr[\s-]*c$", re.IGNORECASE), "process area c"),
    (re.compile(r"^process(?:\s+area)?\s+c$", re.IGNORECASE), "process area c"),
    (re.compile(r"^ut[\s-]*a$", re.IGNORECASE), "utility area"),
    (re.compile(r"^utilities$", re.IGNORECASE), "utility area"),
    (re.compile(r"^utility\s+area$", re.IGNORECASE), "utility area"),
)


def normalize_location(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    for pattern, canonical in _LOCATION_ALIASES:
        if pattern.fullmatch(text):
            return canonical
    return text.casefold()


def _area_base_and_code(normalized: str) -> Tuple[str, Optional[str]]:
    parts = normalized.split()
    if len(parts) >= 2 and re.fullmatch(r"[a-z0-9]{1,3}", parts[-1]):
        return " ".join(parts[:-1]), parts[-1]
    return normalized, None


def score_location(
    report_locations,
    candidate_location: Optional[str],
    fuzzy_match_floor: int,
) -> SignalResult:
    report_value = _best_report_value(report_locations)
    candidate_value = (candidate_location or "").strip() or None

    if not report_value and not candidate_value:
        return SignalResult(0.0, False, False, [])
    if not report_value:
        return SignalResult(0.0, False, False, ["Candidate has a location but report does not mention one"])
    if not candidate_value:
        return SignalResult(
            0.0,
            False,
            False,
            [f"Report mentions location {report_value} but candidate has no location on file"],
        )

    report_norm = normalize_location(report_value)
    candidate_norm = normalize_location(candidate_value)
    if report_norm and candidate_norm and report_norm == candidate_norm:
        return SignalResult(1.0, True, False, [f"Exact location match: {report_value}"])

    report_base, report_code = _area_base_and_code(report_norm or "")
    candidate_base, candidate_code = _area_base_and_code(candidate_norm or "")
    if (
        report_code
        and candidate_code
        and report_base == candidate_base
        and report_code != candidate_code
    ):
        return SignalResult(
            0.0,
            True,
            True,
            [f"Location mismatch: report={report_value} candidate={candidate_value}"],
        )

    raw = fuzz.ratio(report_norm or "", candidate_norm or "")
    if raw >= fuzzy_match_floor:
        score = round(raw / 100.0, 4)
        return SignalResult(
            score,
            True,
            False,
            [
                f"Partial location match: report={report_value} candidate={candidate_value} (similarity={score:.2f})"
            ],
        )

    return SignalResult(
        0.0,
        True,
        True,
        [f"Location mismatch: report={report_value} candidate={candidate_value}"],
    )
