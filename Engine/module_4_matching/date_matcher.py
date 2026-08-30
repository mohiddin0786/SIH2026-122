"""
module_4_matching/date_matcher.py — Date-plausibility scoring signal.

WHY THIS EXISTS:
    Activities on the same equipment tag are strictly sequenced
    (Install -> Weld -> Inspect -> Hydrotest), each with its own planned
    window in the baseline schedule. When a report's equipment tag matches
    several candidates equally (e.g. "spool erected" could be Install SP-101,
    Weld SP-101, or Inspect SP-101), semantic/equipment/activity signals can
    tie or nearly tie. This scorer breaks that tie using report_date vs. each
    candidate's planned_start/planned_finish — a signal semantic text alone
    cannot see.

    This is intentionally a SOFT scorer blended into the weighted composite
    (see config.py / scorer.py), not a hard veto. Reports are sometimes
    logged out of order, and schedule slippage is normal, so being outside
    the planned window should reduce a candidate's score, not disqualify it.

DEGRADATION:
    If report_date is missing/unparseable, or the candidate has no
    planned_start/planned_finish, the signal is not computable (0.0, False)
    and combine_signals() renormalizes weights over the remaining signals —
    exactly like every other Module 4 signal.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from .equipment_matcher import SignalResult

# Grace window (days) around the planned start/finish where a report is
# treated as fully on-time. Field reporting lag and minor schedule noise
# are common and should not be penalized.
_ON_TIME_BUFFER_DAYS = 7

# Beyond the buffer, score decays with distance from the planned window.
# These divisors control how quickly "too early" / "too late" drag the
# score down. Tuned to be forgiving of normal slippage while still
# clearly separating candidates whose windows don't fit at all.
_EARLY_DECAY_DAYS = 45.0
_LATE_DECAY_DAYS = 180.0

# An early-side violation this large (report predates planned_start by
# more than this many days) is treated as a confident contradiction, not
# just a soft penalty — e.g. reporting "hydrotest complete" 4 months
# before hydrotest was ever scheduled to start is a real mismatch, not
# reporting lag.
_CONFIDENT_EARLY_CONTRADICTION_DAYS = 60


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        # Last resort: fromisoformat handles e.g. full ISO timestamps.
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def score_date_plausibility(
    report_date: Optional[str],
    candidate_planned_start: Optional[str],
    candidate_planned_finish: Optional[str],
) -> SignalResult:
    """Scores how plausible it is that `report_date` reflects work on a
    candidate whose planned window is [planned_start, planned_finish].

    Returns SignalResult(0.0, computable=False, ...) when either date is
    missing or unparseable — never invents a penalty from absent data.
    """
    r_date = _parse_date(report_date)
    start = _parse_date(candidate_planned_start)
    finish = _parse_date(candidate_planned_finish)

    if r_date is None or start is None or finish is None:
        return SignalResult(0.0, False, False, [])

    # Defensive: some rows may have finish < start due to upstream data
    # issues. Don't crash Module 4 over a bad schedule row — just widen
    # the window to whichever order they actually come in.
    window_start, window_finish = (start, finish) if start <= finish else (finish, start)

    if window_start - _within_buffer(_ON_TIME_BUFFER_DAYS) <= r_date <= window_finish + _within_buffer(_ON_TIME_BUFFER_DAYS):
        return SignalResult(
            1.0,
            True,
            False,
            [f"Report date {r_date.isoformat()} falls within planned window {window_start.isoformat()} to {window_finish.isoformat()}"],
        )

    if r_date < window_start:
        early_days = (window_start - r_date).days - _ON_TIME_BUFFER_DAYS
        score = max(0.0, 1.0 - (early_days / _EARLY_DECAY_DAYS))
        contradiction = early_days > _CONFIDENT_EARLY_CONTRADICTION_DAYS
        return SignalResult(
            round(score, 4),
            True,
            contradiction,
            [
                f"Report date {r_date.isoformat()} is {early_days + _ON_TIME_BUFFER_DAYS} day(s) "
                f"before planned start {window_start.isoformat()} — too early to plausibly be this activity"
            ],
        )

    # r_date > window_finish (late / slipped schedule) — soft penalty only,
    # never a contradiction: slippage is normal in execution.
    late_days = (r_date - window_finish).days - _ON_TIME_BUFFER_DAYS
    score = max(0.2, 1.0 - (late_days / _LATE_DECAY_DAYS))
    return SignalResult(
        round(score, 4),
        True,
        False,
        [
            f"Report date {r_date.isoformat()} is {late_days + _ON_TIME_BUFFER_DAYS} day(s) "
            f"after planned finish {window_finish.isoformat()} — plausible schedule slippage"
        ],
    )


def _within_buffer(days: int):
    from datetime import timedelta

    return timedelta(days=days)