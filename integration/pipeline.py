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
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

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
from Engine.module_2_extraction.extractor import extract_information
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
        """
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
            ranking = rank_candidates(extracted, candidates)
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
