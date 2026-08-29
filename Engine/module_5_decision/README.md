# Module 5 — Decision Engine

## Purpose

Module 5 converts the ranked candidate output from Module 4 into a final decision for each report.

It classifies the result into one of three states:

- `AUTO_MATCH`
- `HUMAN_REVIEW`
- `UNMATCHED`

## Input

`RankingResult`

Produced by Module 4.

## Output

`DecisionResult`

Defined in the shared schemas.

## Decision Logic

The current rule-based thresholds are:

- Auto-match threshold: `0.85`
- Human-review threshold: `0.60`
- Minimum score gap: `0.10`

### AUTO_MATCH

Used when:

- the best candidate score is at least `0.85`
- and it is sufficiently separated from the second candidate

### HUMAN_REVIEW

Used when:

- the best candidate is plausible
- but the score is not high enough for auto-match
- or the top two candidates are too close

### UNMATCHED

Used when:

- no candidates exist
- or the best candidate score is below `0.60`

## Tests

Run:

```bash
python -m pytest Engine/module_5_decision/tests/test_decision.py -v