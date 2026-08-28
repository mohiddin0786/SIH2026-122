"""
shared/ — Frozen contract package for the AI-Assisted Project Execution
Intelligence System (SIH26122).

Every module (1-7) imports from here. Nobody redefines these models.
This package is frozen after MASTER 0 review — do not edit without
explicit team approval and a version bump.
"""

from .constants import (
    EventType,
    DecisionType,
    ExecutionStatus,
    UpdateStatus,
    ActivityType,
    LabelType,
)
from .exceptions import (
    PipelineError,
    ValidationError,
    NormalizationError,
    ExtractionError,
    RetrievalError,
    MatchingError,
    DecisionError,
    ScheduleUpdateError,
    EvaluationError,
)
from .schemas import (
    RawReportInput,
    NormalizedReport,
    ExtractedEntity,
    ExtractedNumericValue,
    ExtractedReport,
    RetrievalSignals,
    RetrievedCandidate,
    CandidateRetrievalResult,
    MatchingScores,
    RankedCandidate,
    RankingResult,
    DecisionResult,
    ExecutionState,
    UpdateResult,
    GroundTruthRecord,
    EvaluationResult,
)

__version__ = "1.0.0"

__all__ = [
    # constants
    "EventType",
    "DecisionType",
    "ExecutionStatus",
    "UpdateStatus",
    "ActivityType",
    "LabelType",
    # exceptions
    "PipelineError",
    "ValidationError",
    "NormalizationError",
    "ExtractionError",
    "RetrievalError",
    "MatchingError",
    "DecisionError",
    "ScheduleUpdateError",
    "EvaluationError",
    # schemas
    "RawReportInput",
    "NormalizedReport",
    "ExtractedEntity",
    "ExtractedNumericValue",
    "ExtractedReport",
    "RetrievalSignals",
    "RetrievedCandidate",
    "CandidateRetrievalResult",
    "MatchingScores",
    "RankedCandidate",
    "RankingResult",
    "DecisionResult",
    "ExecutionState",
    "UpdateResult",
    "GroundTruthRecord",
    "EvaluationResult",
]