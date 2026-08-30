"""
shared/schemas.py — Official data contracts passed between pipeline modules.

Pipeline:
    RawReportInput
      -> Module 1 (Normalization)      -> NormalizedReport
      -> Module 2 (Extraction)         -> ExtractedReport
      -> Module 3 (Candidate Retrieval)-> CandidateRetrievalResult
      -> Module 4 (Matching & Ranking) -> RankingResult
      -> Module 5 (Confidence/Decision)-> DecisionResult
      -> Module 6 (Schedule Update)    -> UpdateResult

    (System Predictions + Ground Truth) -> Module 7 (Evaluation) -> EvaluationResult

RULES (see Common Integration Contract):
  - report_id is preserved verbatim through every stage.
  - Unknown single values -> None (never "N/A", "-", "{}").
  - Empty collections -> [].
  - All confidence / similarity scores are floats in [0.0, 1.0].
  - Ground truth is never used outside Module 7.
  - Baseline schedule fields (planned_*) are never mutated by modules;
    execution state is tracked separately (see ExecutionState).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .constants import (
    ActivityType,
    DecisionType,
    EventType,
    ExecutionStatus,
    LabelType,
    UpdateStatus,
)

# ---------------------------------------------------------------------------
# Shared validation helper
# ---------------------------------------------------------------------------

UNIT_SCORE_FIELD = Field(
    ..., ge=0.0, le=1.0, description="Score in the range 0.0-1.0 (inclusive)."
)
OPTIONAL_UNIT_SCORE_FIELD = Field(
    default=None, ge=0.0, le=1.0, description="Optional score in 0.0-1.0."
)


# ---------------------------------------------------------------------------
# 1. RawReportInput  (pipeline entry point)
# ---------------------------------------------------------------------------

class RawReportInput(BaseModel):
    """A single unstructured field report as received from the field."""

    report_id: str = Field(..., min_length=1, description="Primary identifier. Preserved end-to-end.")
    report_date: Optional[str] = Field(default=None, description="ISO date, e.g. 2026-08-28.")
    source_type: Optional[str] = Field(default=None, description="e.g. 'daily_diary', 'spreadsheet', 'free_text'.")
    raw_text: str = Field(..., min_length=1, description="Untouched original text. Never modified downstream.")

    @field_validator("report_id")
    @classmethod
    def report_id_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("report_id must not be blank")
        return v


# ---------------------------------------------------------------------------
# 2. NormalizedReport  (Module 1 output)
# ---------------------------------------------------------------------------

class NormalizedReport(BaseModel):
    """Cleaned, standardized text. No entity extraction happens here."""

    report_id: str
    original_text: str = Field(..., description="Verbatim copy of raw_text. Never modified.")
    normalized_text: str = Field(..., description="Cleaned/standardized text.")
    normalization_flags: List[str] = Field(default_factory=list, description="e.g. 'typo_corrected'.")


# ---------------------------------------------------------------------------
# 3-4. Generic extracted value wrappers (Module 2 building blocks)
# ---------------------------------------------------------------------------

class ExtractedEntity(BaseModel):
    """A single extracted string-valued entity (equipment tag, location, activity type)."""

    value: str
    confidence: float = UNIT_SCORE_FIELD


class ExtractedNumericValue(BaseModel):
    """A single extracted numeric value (e.g. progress %) with confidence.
    value is None when it cannot be reliably determined — never invented."""

    value: Optional[float] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("value")
    @classmethod
    def progress_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("numeric value (progress) must be within 0-100")
        return v


class ActivityTypeValue(BaseModel):
    """Activity type classification result. value is None/UNKNOWN when unclear."""

    value: Optional[ActivityType] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class EventTypeValue(BaseModel):
    """Event type classification result."""

    value: EventType = EventType.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# 5. ExtractedReport  (Module 2 output)
# ---------------------------------------------------------------------------

class ExtractedReport(BaseModel):
    """Structured entities extracted from a NormalizedReport."""

    report_id: str
    normalized_text: str
    equipment_tags: List[ExtractedEntity] = Field(default_factory=list)
    locations: List[ExtractedEntity] = Field(default_factory=list)
    activity_type: ActivityTypeValue = Field(default_factory=ActivityTypeValue)
    event_type: EventTypeValue = Field(default_factory=EventTypeValue)
    progress: ExtractedNumericValue = Field(default_factory=ExtractedNumericValue)
    extraction_flags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6-8. Candidate retrieval (Module 3 output)
# ---------------------------------------------------------------------------

class RetrievalSignals(BaseModel):
    """Sub-signals that contributed to a candidate's retrieval_score.
    Any signal may be None if that signal was not computable."""

    semantic_score: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    equipment_match: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    location_match: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    activity_match: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD


class RetrievedCandidate(BaseModel):
    """One schedule activity returned as a candidate by Module 3."""

    activity_id: str
    activity_name: str
    equipment_tag: Optional[str] = None
    location: Optional[str] = None
    discipline: Optional[str] = None
    wbs: Optional[str] = None
    planned_start: Optional[str] = Field(default=None, description="ISO date from schedule_master, e.g. 2026-08-28. Never mutated.")
    planned_finish: Optional[str] = Field(default=None, description="ISO date from schedule_master, e.g. 2026-09-10. Never mutated.")
    retrieval_score: float = UNIT_SCORE_FIELD
    retrieval_signals: RetrievalSignals = Field(default_factory=RetrievalSignals)


class CandidateRetrievalResult(BaseModel):
    """Module 3 output: a small, imperfect candidate set for Module 4 to rank.
    Candidates are sorted by retrieval_score descending; activity_id is unique."""

    report_id: str
    top_k: int = Field(..., ge=0)
    candidates: List[RetrievedCandidate] = Field(default_factory=list)

    @field_validator("candidates")
    @classmethod
    def no_duplicate_activity_ids(cls, v: List[RetrievedCandidate]) -> List[RetrievedCandidate]:
        ids = [c.activity_id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("candidates must not contain duplicate activity_id values")
        return v


# ---------------------------------------------------------------------------
# 9-11. Matching & ranking (Module 4 output)
# ---------------------------------------------------------------------------

class MatchingScores(BaseModel):
    """Explainable per-candidate scoring breakdown."""

    semantic_score: float = UNIT_SCORE_FIELD
    equipment_score: float = UNIT_SCORE_FIELD
    location_score: float = UNIT_SCORE_FIELD
    activity_score: float = UNIT_SCORE_FIELD
    discipline_score: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    date_score: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    contradiction_penalty: float = Field(..., ge=0.0, le=1.0)
    final_score: float = UNIT_SCORE_FIELD


class RankedCandidate(BaseModel):
    """One candidate after detailed matching, with a human-readable explanation."""

    rank: int = Field(..., ge=1)
    activity_id: str
    activity_name: str
    scores: MatchingScores
    explanation: List[str] = Field(default_factory=list)


class RankingResult(BaseModel):
    """Module 4 output. ranked_candidates sorted by scores.final_score descending."""

    report_id: str
    ranked_candidates: List[RankedCandidate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 12. DecisionResult  (Module 5 output)
# ---------------------------------------------------------------------------

class DecisionResult(BaseModel):
    """Module 5 output: the final AUTO_MATCH / HUMAN_REVIEW / UNMATCHED call.

    RULES:
      - AUTO_MATCH  -> selected_activity_id MUST be set.
      - HUMAN_REVIEW-> selected_activity_id MAY hold the leading candidate,
                       but is not confirmed.
      - UNMATCHED   -> selected_activity_id MUST be None.
    """

    report_id: str
    decision: DecisionType
    selected_activity_id: Optional[str] = None
    confidence: float = UNIT_SCORE_FIELD
    best_score: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    second_best_score: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    score_gap: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    decision_reasons: List[str] = Field(default_factory=list)

    @field_validator("selected_activity_id")
    @classmethod
    def auto_match_requires_selection(cls, v, info):
        decision = info.data.get("decision")
        if decision == DecisionType.AUTO_MATCH and not v:
            raise ValueError("AUTO_MATCH requires a non-null selected_activity_id")
        if decision == DecisionType.UNMATCHED and v is not None:
            raise ValueError("UNMATCHED requires selected_activity_id to be None")
        return v


# ---------------------------------------------------------------------------
# 13. ExecutionState  (tracked separately from baseline schedule)
# ---------------------------------------------------------------------------

class ExecutionState(BaseModel):
    """As-built execution state for one activity_id.
    Never confuse with baseline planning fields (planned_start/finish/duration),
    which live only in the read-only Schedule Master."""

    activity_id: str
    actual_status: ExecutionStatus = ExecutionStatus.UNKNOWN
    actual_progress: Optional[float] = None
    last_report_id: Optional[str] = None
    last_update_timestamp: Optional[str] = None  # ISO-8601, e.g. 2026-08-28T14:30:00Z

    @field_validator("actual_progress")
    @classmethod
    def progress_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("actual_progress must be within 0-100")
        return v


# ---------------------------------------------------------------------------
# 14. UpdateResult  (Module 6 output)
# ---------------------------------------------------------------------------

class UpdateResult(BaseModel):
    """Module 6 output. Only AUTO_MATCH decisions may produce UPDATED."""

    report_id: str
    update_status: UpdateStatus
    activity_id: Optional[str] = None
    previous_execution_state: Optional[ExecutionState] = None
    new_execution_state: Optional[ExecutionState] = None
    update_reason: str = ""


# ---------------------------------------------------------------------------
# Ground truth (evaluation input only — never used at prediction time)
# ---------------------------------------------------------------------------

class GroundTruthRecord(BaseModel):
    """One row of ground_truth_v2.csv. Used exclusively by Module 7."""

    report_id: str
    correct_activity_id: Optional[str] = None
    label_type: LabelType
    verification_source: Optional[str] = None


# ---------------------------------------------------------------------------
# 15. EvaluationResult  (Module 7 output)
# ---------------------------------------------------------------------------

class ConfusionCell(BaseModel):
    predicted: str
    actual: str
    count: int = Field(..., ge=0)


class CategoryMetric(BaseModel):
    category: str
    count: int = Field(..., ge=0)
    accuracy: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    precision: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    recall: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    f1: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD


class UnmatchedMetrics(BaseModel):
    precision: float = UNIT_SCORE_FIELD
    recall: float = UNIT_SCORE_FIELD
    f1: float = UNIT_SCORE_FIELD


class EvaluationResult(BaseModel):
    """Module 7 output: aggregate performance of the pipeline vs. ground truth."""

    total_reports: int = Field(..., ge=0)
    evaluated_reports: int = Field(..., ge=0)
    excluded_ambiguous: int = Field(..., ge=0)
    exact_match_accuracy: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    auto_match_accuracy: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    human_review_rate: Optional[float] = OPTIONAL_UNIT_SCORE_FIELD
    unmatched_metrics: Optional[UnmatchedMetrics] = None
    confusion_matrix: List[ConfusionCell] = Field(default_factory=list)
    category_metrics: List[CategoryMetric] = Field(default_factory=list)
    misclassified_examples: List[str] = Field(default_factory=list)