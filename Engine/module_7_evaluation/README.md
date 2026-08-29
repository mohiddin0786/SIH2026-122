# Module 7 — Evaluation and Performance Analytics

This module evaluates system DecisionResult predictions against the
ground-truth dataset.

## Inputs

- DecisionResult predictions
- ground_truth_v1.csv

## Metrics

- Exact-match accuracy
- AUTO_MATCH accuracy
- HUMAN_REVIEW rate
- UNMATCHED precision, recall and F1
- Confusion matrix
- Category-wise metrics
- Misclassified examples

AMBIGUOUS reports are excluded from exact-match accuracy by default.

## Ground Truth Isolation

Ground truth is used only inside Module 7 and never flows back to
Modules 1–6.

## Validation

The output is validated using:

EvaluationResult(**result)