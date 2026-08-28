# shared/ — Frozen Integration Contract

Version: 1.0.0 (tag: `shared-v1.0`)

This package is the single source of truth for every data structure
passed between Modules 1–7. **All modules import from here. Nobody
redefines these models locally.**

## Pipeline

```
RawReportInput
  -> Module 1 (Normalization)        -> NormalizedReport
  -> Module 2 (Extraction)           -> ExtractedReport
  -> Module 3 (Candidate Retrieval)  -> CandidateRetrievalResult
  -> Module 4 (Matching & Ranking)   -> RankingResult
  -> Module 5 (Confidence/Decision)  -> DecisionResult
  -> Module 6 (Schedule Update)      -> UpdateResult

(System predictions + GroundTruthRecord) -> Module 7 (Evaluation) -> EvaluationResult
```

## Files

- `schemas.py` — Pydantic models for every stage above (the contract itself).
- `constants.py` — Enums: `EventType`, `DecisionType`, `ExecutionStatus`,
  `UpdateStatus`, `ActivityType`, `LabelType`. Use these — never invent
  alternative string values.
- `exceptions.py` — `PipelineError` and subclasses, one per module. All
  carry an optional `report_id` for traceability; use `.to_dict()` for
  structured logging.
- `examples/` — one canonical JSON payload per pipeline stage. **Use
  these to build/test your module before an upstream teammate's real
  code exists.**

## Rules (see Common Integration Contract for full text)

1. Import, don't redefine.
2. Don't rename contract fields.
3. Preserve `report_id` verbatim through every stage.
4. Use shared Enums — no alternative spellings.
5. All confidence/similarity scores: `0.0–1.0`. Progress: `0–100`.
6. Unknown single value → `null`. No items → `[]`. Never `"N/A"`, `"-"`, `{}`.
7. Stay inside your module's responsibility.
8. Your `main` function accepts the official input schema, returns the
   official output schema.
9. `data/schedule_master_v1.csv`, `raw_reports_v1.csv`,
   `ground_truth_v1.csv` are read-only.
10. Ground truth (`GroundTruthRecord`) is used **only** inside Module 7.
    Never let it influence normalization/extraction/retrieval/matching/decision.
11. Baseline schedule fields (`planned_start`, `planned_finish`,
    `planned_duration_days`) are never written by any module.
    Actual execution state lives only in `ExecutionState`.
12. Keep thresholds/weights/top_k/aliases configurable, not hardcoded.

## Contract enforcement built into the schema

- `DecisionResult` rejects `AUTO_MATCH` with no `selected_activity_id`,
  and rejects `UNMATCHED` with a non-null `selected_activity_id` — this
  is a Pydantic validator, not just documentation, so a violating
  module fails fast at construction time.
- `CandidateRetrievalResult` rejects duplicate `activity_id`s.
- `ExtractedNumericValue.value` (progress) and `ExecutionState.actual_progress`
  are range-checked to `0–100`; all score fields to `0.0–1.0`.

## Data leakage warning for Module 1/2 authors

`raw_reports_v1.csv` contains `report_category`, `expected_event_type`,
and `expected_progress` columns. **These are evaluation-only labels
and must never be read by any prediction module** — only `report_id`,
`report_date`, `source_type`, `raw_text` (i.e. exactly `RawReportInput`'s
fields) are legitimate input.

## Before you write any module code

1. `pip install -r requirements.txt`
2. `pytest tests/test_shared_contract.py -v` — should be green.
3. Read `shared/examples/*.json` for your module's exact input/output shape.
4. Build against those examples; swap in real upstream output once it exists.
