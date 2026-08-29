"""
integration/ — End-to-end pipeline integrating all 7 SIH2K26 modules.

Pipeline:
    RawReportInput
      → Module 1 (Normalization)      → NormalizedReport
      → Module 2 (Extraction)         → ExtractedReport
      → Module 3 (Candidate Retrieval)→ CandidateRetrievalResult
      → Module 4 (Matching & Ranking) → RankingResult
      → Module 5 (Decision)           → DecisionResult
      → Module 6 (Schedule Update)    → UpdateResult
      → Module 7 (Evaluation)         → EvaluationResult (optional)

Usage:
    from integration.pipeline import Pipeline, process_report, process_batch

    # Single report
    result = process_report(raw_report)

    # Batch processing with optional evaluation
    pipeline = Pipeline()
    results = pipeline.process_batch(raw_reports)
    evaluation = pipeline.evaluate(predictions=results, ground_truth=truth_df)
"""

from .pipeline import Pipeline, process_report, process_batch, _load_schedule_index

__all__ = [
    "Pipeline",
    "process_report",
    "process_batch",
    "_load_schedule_index",
]

__version__ = "1.0.0"
