"""
module_3_candidate/retriever.py — MODULE 3: CANDIDATE RETRIEVAL.

RESPONSIBILITY:
    Given an ExtractedReport, reduce the full schedule (118+ activities) to a
    small top-K candidate set for Module 4 (Matching & Ranking) to score in
    detail. This module does NOT decide the final match, does NOT read
    ground truth, and must degrade gracefully when report metadata is sparse
    (falls back to semantic similarity alone).

CORE FUNCTIONS:
    build_schedule_index(schedule_path_or_dataframe) -> ScheduleIndex
    retrieve_candidates(report, index, top_k=5) -> CandidateRetrievalResult

STRATEGY (hybrid, weighted):
    - equipment_match : exact / fuzzy match of extracted equipment tags
                        against schedule `equipment_tag`
    - location_match  : exact / fuzzy match of extracted locations
                        against schedule `location`
    - activity_match  : fuzzy match of extracted activity_type against
                        schedule `activity_name` (+ description)
    - semantic_score  : cosine similarity between report text and
                        activity_name + activity_description embeddings

    retrieval_score = weighted sum of whichever signals are computable.
    A signal is left as None (not 0.0) when it genuinely can't be computed
    (e.g. no equipment tags were extracted from the report at all), per the
    RetrievalSignals contract. Missing signals do not zero out the score —
    weights are renormalized over the signals that ARE present, so a report
    with only free text still gets a meaningful semantic-only score.

    Ties on retrieval_score are broken deterministically by activity_id
    (ascending), so results are stable regardless of the schedule CSV's
    row order.

NOTE ON CandidateRetrievalResult.top_k:
    top_k on the returned result reflects the ACTUAL number of candidates
    returned (len(candidates)), not the requested top_k argument. If the
    schedule has fewer activities than requested, these can differ — a
    consumer iterating on result.top_k should always match len(result.candidates).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from shared.exceptions import RetrievalError
from shared.schemas import (
    CandidateRetrievalResult,
    ExtractedReport,
    RetrievalSignals,
    RetrievedCandidate,
)

from .semantic_backend import SemanticBackend

logger = logging.getLogger(__name__)

# Required columns per the frozen schedule_master_v1.csv contract.
REQUIRED_SCHEDULE_COLUMNS = [
    "activity_id",
    "project_id",
    "wbs",
    "discipline",
    "activity_name",
    "activity_description",
    "equipment_tag",
    "location",
    "work_package",
    "predecessor_activity_id",
    "planned_start",
    "planned_finish",
    "planned_duration_days",
    "baseline_status",
]

# Weights for the hybrid score. Renormalized at query time over whichever
# signals are actually computable for a given (report, candidate) pair.
SIGNAL_WEIGHTS = {
    "equipment_match": 0.35,
    "location_match": 0.20,
    "activity_match": 0.15,
    "semantic_score": 0.30,
}

FUZZY_MATCH_FLOOR = 40  # rapidfuzz ratio below this -> confirmed non-match (0.0), not None
_TAG_BODY_RE = re.compile(r"^([A-Z]+)(\d{3,4})$")


def _clean(value: object) -> Optional[str]:
    """CSV-blank / NaN -> None. Never returns 'nan', '-', 'N/A' etc."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "n/a", "na", "-", "none"}:
        return None
    return text


def _normalize_equipment_tag(value: Optional[str]) -> Optional[str]:
    """Canonical tag form so SP-101, sp101, and SP 101 compare equal, and
    SP-101 does not compare equal to P-101 (substring / partial_ratio trap)."""
    if not value:
        return None
    compact = re.sub(r"[\s_\-]+", "", value.strip().upper())
    if not compact:
        return None
    match = _TAG_BODY_RE.fullmatch(compact)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return compact


def _equipment_match_score(query: Optional[str], candidate: Optional[str]) -> Optional[float]:
    if not query or not candidate:
        return None
    query_tag = _normalize_equipment_tag(query)
    candidate_tag = _normalize_equipment_tag(candidate)
    if not query_tag or not candidate_tag:
        return None
    return 1.0 if query_tag == candidate_tag else 0.0


def _location_match_score(query: Optional[str], candidate: Optional[str]) -> Optional[float]:
    """Exact after whitespace/case fold. Area suffixes (A vs B) are a hard
    mismatch so Pump Area A is not scored ~0.95 against Pump Area B."""
    if not query or not candidate:
        return None
    query_norm = " ".join(query.split()).casefold()
    candidate_norm = " ".join(candidate.split()).casefold()
    if query_norm == candidate_norm:
        return 1.0
    query_parts = query_norm.split()
    candidate_parts = candidate_norm.split()
    if (
        len(query_parts) >= 2
        and len(candidate_parts) >= 2
        and query_parts[:-1] == candidate_parts[:-1]
        and query_parts[-1] != candidate_parts[-1]
    ):
        return 0.0
    raw = fuzz.ratio(query_norm, candidate_norm)
    return round(raw / 100.0, 4) if raw >= FUZZY_MATCH_FLOOR else 0.0


def _activity_match_score(query: Optional[str], candidate: Optional[str]) -> Optional[float]:
    """Activity names are free text — partial_ratio is appropriate here."""
    if not query or not candidate:
        return None
    if query.strip().lower() == candidate.strip().lower():
        return 1.0
    raw = fuzz.partial_ratio(query.lower(), candidate.lower())
    return round(raw / 100.0, 4) if raw >= FUZZY_MATCH_FLOOR else 0.0


@dataclass
class ScheduleIndex:
    """Precomputed, reusable index over the schedule master. Built once via
    build_schedule_index(); never rebuilt per-report."""

    df: pd.DataFrame
    embeddings: np.ndarray
    backend: SemanticBackend


def build_schedule_index(
    schedule_path_or_dataframe: Union[str, Path, pd.DataFrame],
    model_name: Optional[str] = None,
) -> ScheduleIndex:
    """Loads schedule_master_v1.csv (or an already-loaded DataFrame),
    validates required columns, and precomputes text embeddings for every
    activity ONCE. This index is reused across all retrieve_candidates()
    calls — do not call this per report.
    """
    if isinstance(schedule_path_or_dataframe, (str, Path)):
        df = pd.read_csv(schedule_path_or_dataframe, dtype=str)
    else:
        df = schedule_path_or_dataframe.copy()

    missing = [c for c in REQUIRED_SCHEDULE_COLUMNS if c not in df.columns]
    if missing:
        raise RetrievalError(f"schedule_master missing required columns: {missing}")

    if len(df) == 0:
        raise RetrievalError("schedule_master is empty — no activities to index")

    if df["activity_id"].isna().any() or (df["activity_id"].astype(str).str.strip() == "").any():
        raise RetrievalError("schedule_master contains blank activity_id values")
    if df["activity_id"].duplicated().any():
        dupes = df.loc[df["activity_id"].duplicated(), "activity_id"].tolist()
        raise RetrievalError(f"schedule_master contains duplicate activity_id values: {dupes}")

    df = df.reset_index(drop=True)

    corpus = [
        f"{_clean(row.activity_name) or ''} {_clean(row.activity_description) or ''}".strip()
        for row in df.itertuples()
    ]

    backend = SemanticBackend(model_name=model_name or "all-MiniLM-L6-v2")
    backend.fit_corpus(corpus)
    embeddings = backend.embed(corpus)

    logger.info(
        "ScheduleIndex built: %d activities (semantic backend: %s)",
        len(df),
        backend.get_mode(),
    )
    return ScheduleIndex(df=df, embeddings=embeddings, backend=backend)


def _best_extracted_value(entities) -> Optional[str]:
    """From a list of ExtractedEntity, pick the highest-confidence value.
    Returns None if the list is empty (nothing extracted for this signal)."""
    if not entities:
        return None
    best = max(entities, key=lambda e: e.confidence)
    return _clean(best.value)


def _weighted_combine(signals: dict) -> float:
    """Renormalizes SIGNAL_WEIGHTS over whichever signals are not None."""
    present = {k: v for k, v in signals.items() if v is not None}
    if not present:
        return 0.0
    weight_sum = sum(SIGNAL_WEIGHTS[k] for k in present)
    if weight_sum == 0:
        return 0.0
    return sum(SIGNAL_WEIGHTS[k] * v for k, v in present.items()) / weight_sum


def retrieve_candidates(
    report: ExtractedReport,
    index: ScheduleIndex,
    top_k: int = 5,
) -> CandidateRetrievalResult:
    """Returns the top_k schedule activities most likely to correspond to
    this report, sorted by retrieval_score descending (ties broken by
    activity_id ascending, for deterministic output). Never raises on
    sparse report metadata — degrades to semantic-only scoring.

    NOTE: the returned CandidateRetrievalResult.top_k reflects the actual
    number of candidates returned, which may be less than the requested
    top_k if the schedule has fewer activities than that.
    """
    if top_k <= 0:
        raise RetrievalError("top_k must be a positive integer", report_id=report.report_id)

    query_equipment = _best_extracted_value(report.equipment_tags)
    query_location = _best_extracted_value(report.locations)
    query_activity = (
        report.activity_type.value.value if report.activity_type and report.activity_type.value else None
    )
    query_text = report.normalized_text or ""

    query_vec = index.backend.embed([query_text])[0]
    sem_scores = index.backend.cosine_sim(query_vec, index.embeddings)
    # Cosine sim can be slightly negative for tfidf/near-orthogonal sbert
    # vectors; clip into the contract's [0, 1] range rather than raising.
    sem_scores = np.clip(sem_scores, 0.0, 1.0)

    scored_rows = []
    for i, row in enumerate(index.df.itertuples()):
        equipment_match = _equipment_match_score(query_equipment, _clean(row.equipment_tag))
        location_match = _location_match_score(query_location, _clean(row.location))
        activity_match = _activity_match_score(query_activity, _clean(row.activity_name))
        semantic_score = float(sem_scores[i]) if len(sem_scores) else None

        signals = {
            "equipment_match": equipment_match,
            "location_match": location_match,
            "activity_match": activity_match,
            "semantic_score": semantic_score,
        }
        final_score = round(_weighted_combine(signals), 4)
        scored_rows.append((final_score, str(row.activity_id), i, signals))

    # Sort by score descending; break ties deterministically by activity_id
    # ascending (not DataFrame row order, which is CSV-load-order-dependent).
    scored_rows.sort(key=lambda x: (-x[0], x[1]))
    top_rows = scored_rows[:top_k]

    candidates: List[RetrievedCandidate] = []
    for final_score, _activity_id, i, signals in top_rows:
        row = index.df.iloc[i]
        candidates.append(
            RetrievedCandidate(
                activity_id=str(row.activity_id),
                activity_name=_clean(row.activity_name) or "",
                equipment_tag=_clean(row.equipment_tag),
                location=_clean(row.location),
                discipline=_clean(row.discipline),
                wbs=_clean(row.wbs),
                retrieval_score=final_score,
                retrieval_signals=RetrievalSignals(**signals),
            )
        )

    return CandidateRetrievalResult(
        report_id=report.report_id,
        top_k=len(candidates),
        candidates=candidates,
    )