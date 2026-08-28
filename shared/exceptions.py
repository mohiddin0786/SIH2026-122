"""
shared/exceptions.py — Common, consistent error types for the pipeline.

Every module should raise these (or subclasses) instead of bare
Exception / silent failure, and should preserve report_id in the
exception where the error is tied to a specific report.
"""

from typing import Optional


class PipelineError(Exception):
    """Base class for all pipeline errors. Carries report_id when known."""

    def __init__(self, message: str, report_id: Optional[str] = None):
        self.message = message
        self.report_id = report_id
        super().__init__(self._format())

    def _format(self) -> str:
        if self.report_id:
            return f"[report_id={self.report_id}] {self.message}"
        return self.message

    def to_dict(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "report_id": self.report_id,
        }


class ValidationError(PipelineError):
    """Input failed schema / contract validation (missing field, bad type, etc.)."""


class NormalizationError(PipelineError):
    """Raised by Module 1 (Normalization)."""


class ExtractionError(PipelineError):
    """Raised by Module 2 (Information Extraction)."""


class RetrievalError(PipelineError):
    """Raised by Module 3 (Candidate Retrieval)."""


class MatchingError(PipelineError):
    """Raised by Module 4 (Matching & Ranking)."""


class DecisionError(PipelineError):
    """Raised by Module 5 (Confidence & Decision)."""


class ScheduleUpdateError(PipelineError):
    """Raised by Module 6 (Schedule Update)."""


class EvaluationError(PipelineError):
    """Raised by Module 7 (Evaluation). Ground truth issues live here."""