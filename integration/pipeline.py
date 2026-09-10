"""
integration/pipeline.py — End-to-end SIH2K26 pipeline.

Orchestrates all 7 modules in order:

    RawReportInput
      → Module 1 (Normalization)      → NormalizedReport
      → Module 2 (Extraction)         → ExtractedReport
      → Module 3 (Candidate Retrieval)→ CandidateRetrievalResult
      → Module 4 (Matching & Ranking) → RankingResult
      → Module 5 (Decision)           → DecisionResult
      → Module 6 (Schedule Update)    → UpdateResult
      → Module 7 (Evaluation)         → EvaluationResult (optional)

The schedule index is built once and reused across all reports, keeping
I/O and embedding-model load overhead minimal.

Multi-activity reports:
    When a single RawReportInput contains multiple independent activities,
    segment_report() splits it into independent sub-reports, each of which
    is processed through the full Module 1-6 pipeline separately.
    See segment_report() and process_segments() below.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from shared.constants import EventType
from shared.exceptions import PipelineError
from shared.schemas import (
    RawReportInput,
    NormalizedReport,
    ExtractedReport,
    CandidateRetrievalResult,
    RankingResult,
    DecisionResult,
    UpdateResult,
    EvaluationResult,
    GroundTruthRecord,
)

from Engine.module_1_normalization.normalizer import normalize_report
from Engine.module_2_extraction.extractor import (
    extract_information,
    EQUIPMENT_TAG_PATTERN,
    extract_event_type,
)
from Engine.module_3_candidate.retriever import (
    ScheduleIndex,
    build_schedule_index,
    retrieve_candidates,
)
from Engine.module_4_matching.ranker import rank_candidates
from Engine.module_5_decision.decision import make_decision
from Engine.module_6_schedule_update.updater import ScheduleUpdater
from Engine.module_6_schedule_update.config import ScheduleUpdateConfig
from Engine.module_7_evaluation.evaluator import evaluate_predictions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline-internal result type
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    """Snapshot of one processing stage for a single report."""

    stage: str  # e.g. "normalization", "extraction", ...
    success: bool
    data: Optional[object] = None  # typed output of the stage
    error: Optional[str] = None
    error_type: Optional[str] = None


@dataclass
class PipelineResult:
    """Complete outcome of running every module for one report.

    Customer-facing summary is available via ``to_summary()``.
    """

    report_id: str
    stages: List[StageResult] = field(default_factory=list)
    evaluated: bool = False
    evaluation: Optional[Dict[str, object]] = None

    # Convenience accessors populated by the pipeline
    normalized_report: Optional[NormalizedReport] = None
    extracted_report: Optional[ExtractedReport] = None
    candidates: Optional[CandidateRetrievalResult] = None
    ranking: Optional[RankingResult] = None
    decision: Optional[DecisionResult] = None
    update: Optional[UpdateResult] = None

    # Multi-activity segmentation: populated when the report
    # was split into independent segments (None for single-activity reports).
    segments: Optional[List["PipelineResult"]] = None

    def failed(self) -> bool:
        """Return True if any stage raised an error."""
        return any(not s.success for s in self.stages)

    def failed_stage(self) -> Optional[StageResult]:
        """Return the first stage that failed, if any."""
        return next((s for s in self.stages if not s.success), None)

    def to_summary(self) -> Dict[str, object]:
        """Return a clean, customer-facing summary dict.

        Does not expose internal schema types or architectural details.
        """
        failed_stage = self.failed_stage()
        if failed_stage:
            return {
                "report_id": self.report_id,
                "status": "FAILED",
                "stage": failed_stage.stage,
                "reason": failed_stage.error,
            }

        summary: Dict[str, object] = {
            "report_id": self.report_id,
            "status": "PROCESSED",
        }

        if self.decision is not None:
            summary["decision"] = self.decision.decision.value
            summary["confidence"] = self.decision.confidence
            summary["selected_activity"] = self.decision.selected_activity_id
            summary["reasons"] = self.decision.decision_reasons

        if self.update is not None:
            summary["update_status"] = self.update.update_status.value
            if self.update.new_execution_state is not None:
                summary["current_progress"] = self.update.new_execution_state.actual_progress
                summary["current_status"] = self.update.new_execution_state.actual_status.value
            summary["update_reason"] = self.update.update_reason

        if self.evaluated:
            summary["evaluated"] = True
            if self.evaluation is not None:
                summary["accuracy"] = self.evaluation.get("exact_match_accuracy")
                summary["human_review_rate"] = self.evaluation.get("human_review_rate")
                summary["misclassified"] = self.evaluation.get("misclassified_examples", [])

        return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_schedule_index(
    schedule_path: str = "Data/schedule_master_v1.csv",
) -> ScheduleIndex:
    """Load and return a ScheduleIndex from the baseline schedule master."""
    return build_schedule_index(schedule_path)


# ---------------------------------------------------------------------------
# Multi-activity report segmentation
# ---------------------------------------------------------------------------

# Strong boundary: period followed by whitespace + uppercase letter,
# or a semicolon.  Avoids splitting on abbreviations and decimals.
_BOUNDARY_RE = re.compile(r"(?<=[.]|;)\s+(?=[A-Z])")

# Evidence rule: a segment must carry an identity signal AND an
# event/progress signal to be processed independently.


def _segment_has_evidence(text: str) -> bool:
    """Return True when *text* contains enough independent evidence to
    represent an activity update.

    Two conditions must both hold (AND):
      1. An identity signal: an equipment tag (F-101, P-888, …) or
         another strong identity marker already present in the project.
      2. An event / progress signal: a recognised event word such as
         started, completed, finished, 50%, progress, etc.

    Contextual phrases (``after inspection approval``, ``because of
    weather``, ``started yesterday and is now 50% complete``) that lack
    either signal are NOT split.
    """
    equipment_tags = EQUIPMENT_TAG_PATTERN.findall(text)
    has_identity = len(equipment_tags) > 0

    if not has_identity:
        return False

    event_type = extract_event_type(text)
    has_event = event_type.value in (
        EventType.START,
        EventType.PROGRESS,
        EventType.FINISH,
    )
    return has_event


def segment_report(report: RawReportInput) -> List[str]:
    """Split a raw report into independent segment strings using only
    strong boundaries.

    Splits on sentence boundaries (``.`` followed by whitespace +
    uppercase letter) or semicolons (``;``).  Each candidate segment is
    then validated by ``_segment_has_evidence``; segments that do not
    satisfy the evidence rule are re-joined with the preceding segment
    rather than processed independently.

    Safety principle: WHEN IN DOUBT, DO NOT SPLIT.
    """
    text = report.raw_text.strip()

    # Quick check: does the text even contain a strong boundary?
    if not _BOUNDARY_RE.search(text):
        return [text]

    raw_segments = _BOUNDARY_RE.split(text)

    # Apply the conservative evidence rule: a segment is only kept
    # as an independent activity when it contains both an identity
    # signal and an event/progress signal.
    segments: List[str] = []
    for seg in raw_segments:
        seg_stripped = seg.strip()
        if not seg_stripped:
            continue
        if segments and not _segment_has_evidence(seg_stripped):
            # Not enough independent evidence — merge with previous.
            segments[-1] = segments[-1] + " " + seg_stripped
        else:
            segments.append(seg_stripped)

    return segments if len(segments) > 1 else [text]


# ---------------------------------------------------------------------------
# Core pipeline class
# ---------------------------------------------------------------------------


class Pipeline:
    """Orchestrates all 7 SIH2K26 modules end-to-end.

    The schedule index is built once at construction time and reused for
    every report, so callers should prefer a single ``Pipeline`` instance
    when processing multiple reports.

    Args:
        schedule_index: Pre-built ScheduleIndex. If None, built from path.
        schedule_master_path: Path to schedule_master_v1.csv (used if no index given).
        retrieve_fn: Optional callable(retrieved_report, index, top_k) -> CandidateRetrievalResult.
            Defaults to ``retrieve_candidates``. Inject a mock for deterministic tests.
        repository: Optional ExecutionStateRepository to inject for testing.
            If None, a default repository is created by ScheduleUpdater.
    """

    def __init__(
        self,
        schedule_index: Optional[ScheduleIndex] = None,
        schedule_master_path: str = "Data/schedule_master_v1.csv",
        retrieve_fn=None,
        repository=None,
    ) -> None:
        if schedule_index is not None:
            self.schedule_index = schedule_index
        else:
            logger.info("Pipeline: building schedule index from %s", schedule_master_path)
            self.schedule_index = _load_schedule_index(schedule_master_path)

        self.config = ScheduleUpdateConfig()
        self._retrieve_fn = retrieve_fn if retrieve_fn is not None else retrieve_candidates
        # Pre-cache the schedule_master DataFrame so updater never reads CSV
        self._schedule_master_df: Optional[pd.DataFrame] = None
        self._repository = repository

    def _get_schedule_master_df(self) -> pd.DataFrame:
        if self._schedule_master_df is None:
            self._schedule_master_df = pd.read_csv(
                self.config.schedule_master_path, dtype=str
            )
        return self._schedule_master_df

    def process_report(
        self,
        raw_report: RawReportInput,
        ground_truth: Optional[object] = None,
    ) -> PipelineResult:
        """Run every module for a single raw report.

        Args:
            raw_report: The unstructured field report to process.
            ground_truth: Optional ground-truth record(s) for Module 7
                evaluation. Accepts DataFrame, CSV path, list of dicts, or
                list of GroundTruthRecord objects.

        Returns:
            PipelineResult with every stage's outcome populated.
            When the report contains multiple independent activities,
            the result carries all segment results in ``.segments``.
        """
        # --- Multi-activity segmentation check ---
        segment_texts = segment_report(raw_report)
        if len(segment_texts) > 1:
            return self.process_segments(raw_report)

        result = PipelineResult(report_id=raw_report.report_id)

        # --- Module 1: Normalization ---
        try:
            normalized = normalize_report(raw_report)
            result.normalized_report = normalized
            result.stages.append(
                StageResult(stage="normalization", success=True, data=normalized)
            )
        except Exception as exc:
            err_msg = f"Normalization failed: {exc}"
            logger.error(err_msg, exc_info=True)
            result.stages.append(
                StageResult(
                    stage="normalization",
                    success=False,
                    error=err_msg,
                    error_type=type(exc).__name__,
                )
            )
            return result

        # --- Module 2: Extraction ---
        try:
            extracted = extract_information(normalized)
            result.extracted_report = extracted
            result.stages.append(
                StageResult(stage="extraction", success=True, data=extracted)
            )
        except Exception as exc:
            err_msg = f"Extraction failed: {exc}"
            logger.error(err_msg, exc_info=True)
            result.stages.append(
                StageResult(
                    stage="extraction",
                    success=False,
                    error=err_msg,
                    error_type=type(exc).__name__,
                )
            )
            return result

        # --- Module 3: Candidate Retrieval ---
        try:
            candidates = self._retrieve_fn(extracted, self.schedule_index, top_k=5)
            result.candidates = candidates
            result.stages.append(
                StageResult(stage="candidate_retrieval", success=True, data=candidates)
            )
        except Exception as exc:
            err_msg = f"Candidate retrieval failed: {exc}"
            logger.error(err_msg, exc_info=True)
            result.stages.append(
                StageResult(
                    stage="candidate_retrieval",
                    success=False,
                    error=err_msg,
                    error_type=type(exc).__name__,
                )
            )
            return result

        # --- Module 4: Matching & Ranking ---
        try:
            ranking = rank_candidates(extracted, candidates, report_date=raw_report.report_date)
            result.ranking = ranking
            result.stages.append(
                StageResult(stage="matching_ranking", success=True, data=ranking)
            )
        except Exception as exc:
            err_msg = f"Matching/ranking failed: {exc}"
            logger.error(err_msg, exc_info=True)
            result.stages.append(
                StageResult(
                    stage="matching_ranking",
                    success=False,
                    error=err_msg,
                    error_type=type(exc).__name__,
                )
            )
            return result

        # --- Module 5: Decision ---
        try:
            decision = make_decision(ranking)
            result.decision = decision
            result.stages.append(
                StageResult(stage="decision", success=True, data=decision)
            )
        except Exception as exc:
            err_msg = f"Decision failed: {exc}"
            logger.error(err_msg, exc_info=True)
            result.stages.append(
                StageResult(
                    stage="decision",
                    success=False,
                    error=err_msg,
                    error_type=type(exc).__name__,
                )
            )
            return result

        # --- Module 6: Schedule Update ---
        try:
            updater = ScheduleUpdater(
                config=self.config,
                schedule_master_df=self._get_schedule_master_df(),
                repository=self._repository,
            )
            update = updater.update_schedule(decision, extracted)
            result.update = update
            result.stages.append(
                StageResult(stage="schedule_update", success=True, data=update)
            )
        except Exception as exc:
            err_msg = f"Schedule update failed: {exc}"
            logger.error(err_msg, exc_info=True)
            result.stages.append(
                StageResult(
                    stage="schedule_update",
                    success=False,
                    error=err_msg,
                    error_type=type(exc).__name__,
                )
            )
            return result

        return result

    def process_segments(self, report: RawReportInput) -> PipelineResult:
        """Split a multi-activity report into independent segments
        and run each through the full Module 1–6 pipeline.

        Each segment receives a unique report_id of the form
        ``{original_report_id}-seg-{N}`` so that Module 6's
        duplicate/idempotency design remains intact and every
        segment is independently auditable.

        If one segment fails, the remaining valid segments are
        still processed and represented in the aggregate result.
        """
        segments_text = segment_report(report)
        original_report_id = report.report_id
        original_report_date = report.report_date
        original_source_type = report.source_type

        segment_results: List[PipelineResult] = []

        for idx, seg_text in enumerate(segments_text, start=1):
            seg_report_id = f"{original_report_id}-seg-{idx}"
            seg_raw = RawReportInput(
                report_id=seg_report_id,
                report_date=original_report_date,
                source_type=original_source_type,
                raw_text=seg_text,
            )
            try:
                seg_result = self.process_report(seg_raw)
            except Exception as exc:
                logger.error(
                    "Segment %d of report %s failed: %s",
                    idx, original_report_id, exc,
                )
                seg_result = PipelineResult(
                    report_id=seg_report_id,
                    stages=[
                        StageResult(
                            stage="pipeline",
                            success=False,
                            error=f"Segment processing failed: {exc}",
                            error_type=type(exc).__name__,
                        )
                    ],
                )
            segment_results.append(seg_result)

        return PipelineResult(
            report_id=original_report_id,
            segments=segment_results,
            stages=[
                StageResult(
                    stage="segmentation",
                    success=True,
                    data=f"{len(segment_results)} segment(s) processed",
                )
            ],
        )

    def process_batch(
        self,
        raw_reports: List[RawReportInput],
        ground_truth: Optional[object] = None,
    ) -> List[PipelineResult]:
        """Process multiple reports and return their PipelineResults.

        A failure in one report does not prevent other reports from being
        processed.
        """
        results: List[PipelineResult] = []
        for report in raw_reports:
            try:
                res = self.process_report(report, ground_truth=ground_truth)
            except Exception as exc:
                logger.error("Unexpected pipeline error for %s: %s", report.report_id, exc)
                res = PipelineResult(
                    report_id=report.report_id,
                    stages=[
                        StageResult(
                            stage="pipeline",
                            success=False,
                            error=f"Unexpected error: {exc}",
                            error_type=type(exc).__name__,
                        )
                    ],
                )
            results.append(res)
        return results

    def evaluate(
        self,
        predictions: List[DecisionResult],
        ground_truth: object,
    ) -> Dict[str, object]:
        """Run Module 7 evaluation on predictions vs ground truth.

        Args:
            predictions: DecisionResult objects (typically from pipeline outputs).
            ground_truth: Ground truth records (DataFrame, CSV path, list, etc.).

        Returns:
            Dict compatible with EvaluationResult schema.
        """
        return evaluate_predictions(predictions=predictions, ground_truth=ground_truth)


# ---------------------------------------------------------------------------
# Convenience functions (stateless, for simple one-off use)
# ---------------------------------------------------------------------------


def process_report(
    raw_report: RawReportInput,
    schedule_master_path: str = "Data/schedule_master_v1.csv",
    ground_truth: Optional[object] = None,
) -> PipelineResult:
    """Process a single raw report through all 7 modules.

    Builds a fresh schedule index each call — prefer ``Pipeline`` for batch
    processing where the index should be reused.
    """
    pipeline = Pipeline(schedule_master_path=schedule_master_path)
    return pipeline.process_report(raw_report, ground_truth=ground_truth)


def process_batch(
    raw_reports: List[RawReportInput],
    schedule_master_path: str = "Data/schedule_master_v1.csv",
    ground_truth: Optional[object] = None,
) -> List[PipelineResult]:
    """Process multiple raw reports through all 7 modules.

    Builds a fresh schedule index each call — prefer ``Pipeline`` for batch
    processing where the index should be reused.
    """
    pipeline = Pipeline(schedule_master_path=schedule_master_path)
    return pipeline.process_batch(raw_reports, ground_truth=ground_truth)


def _load_schedule_index(
    schedule_path: str = "Data/schedule_master_v1.csv",
) -> ScheduleIndex:
    """Load a ScheduleIndex for testing or external use.

    Exposed for use in integration tests that need a fresh index.
    """
    return build_schedule_index(schedule_path)