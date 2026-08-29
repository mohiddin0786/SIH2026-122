"""
Module 7 — Evaluation and Performance Analytics

Ground truth is used ONLY inside this module.
Ground truth must never flow back into Modules 1–6.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from shared.schemas import (
    DecisionResult,
    GroundTruthRecord,
    EvaluationResult,
)
from shared.constants import DecisionType, LabelType
from shared.exceptions import EvaluationError


def _optional_str(value: Any) -> Optional[str]:
    """CSV NaN / blank -> None so GroundTruthRecord stays on the shared contract."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or None


def _ground_truth_record_from_mapping(record: Dict[str, Any]) -> GroundTruthRecord:
    payload = {
        "report_id": _optional_str(record.get("report_id")),
        "correct_activity_id": _optional_str(record.get("correct_activity_id")),
        "label_type": _optional_str(record.get("label_type")),
        "verification_source": _optional_str(record.get("verification_source")),
    }
    try:
        return GroundTruthRecord(**payload)
    except Exception as exc:
        raise EvaluationError(
            f"Invalid ground-truth row for report_id={payload.get('report_id')!r}: {exc}",
            report_id=payload.get("report_id"),
        ) from exc


def _to_ground_truth_records(
    ground_truth: Any,
) -> List[GroundTruthRecord]:
    """
    Convert supported ground-truth inputs into GroundTruthRecord objects.

    Supported inputs:
    - pandas DataFrame
    - CSV file path
    - list of GroundTruthRecord objects
    - list of dictionaries
    """

    if isinstance(ground_truth, pd.DataFrame):
        return [
            _ground_truth_record_from_mapping(record)
            for record in ground_truth.to_dict(orient="records")
        ]

    if isinstance(ground_truth, (str, Path)):
        df = pd.read_csv(ground_truth)
        return [
            _ground_truth_record_from_mapping(record)
            for record in df.to_dict(orient="records")
        ]

    records = list(ground_truth)
    result = []

    for record in records:
        if isinstance(record, GroundTruthRecord):
            result.append(record)
        elif isinstance(record, dict):
            result.append(_ground_truth_record_from_mapping(record))
        else:
            raise TypeError(
                "ground_truth must contain "
                "GroundTruthRecord objects or dictionaries"
            )

    return result


def _to_prediction_records(
    predictions: Iterable[Any],
) -> List[DecisionResult]:
    """Convert predictions into DecisionResult objects."""

    result = []

    for prediction in predictions:

        if isinstance(prediction, DecisionResult):
            result.append(prediction)

        elif isinstance(prediction, dict):
            result.append(
                DecisionResult(**prediction)
            )

        else:
            raise TypeError(
                "predictions must contain "
                "DecisionResult objects or dictionaries"
            )

    return result


def _safe_metric(value: float) -> float:
    """Keep metric values between 0 and 1."""

    return max(
        0.0,
        min(1.0, float(value))
    )


def evaluate_predictions(
    predictions: Iterable[Any],
    ground_truth: Any,
    config: Optional[Dict[str, Any]] = None,
) -> EvaluationResult:
    """
    Evaluate system predictions against ground truth.

    Parameters
    ----------
    predictions:
        DecisionResult objects or dictionaries.

    ground_truth:
        GroundTruthRecord objects, dictionaries,
        pandas DataFrame, or CSV path.

    config:
        Optional configuration.

        exclude_ambiguous:
            If True, AMBIGUOUS reports are excluded
            from exact-match accuracy.

    Returns
    -------
    EvaluationResult
        Official Module 7 output schema.
    """

    config = config or {}

    exclude_ambiguous = config.get(
        "exclude_ambiguous",
        True
    )

    prediction_records = _to_prediction_records(
        predictions
    )

    truth_records = _to_ground_truth_records(
        ground_truth
    )

    truth_by_report = {
        record.report_id: record
        for record in truth_records
    }

    prediction_by_report = {
        record.report_id: record
        for record in prediction_records
    }

    total_reports = len(truth_records)

    # ---------------------------------------------------------------
    # AMBIGUOUS reports
    # ---------------------------------------------------------------

    excluded_ambiguous = sum(
        1
        for record in truth_records
        if record.label_type == LabelType.AMBIGUOUS
    )

    # Reports included in exact-match evaluation.
    if exclude_ambiguous:

        evaluated_truth = [
            record
            for record in truth_records
            if record.label_type
            != LabelType.AMBIGUOUS
        ]

    else:

        evaluated_truth = truth_records

    evaluated_reports = len(evaluated_truth)

    # ---------------------------------------------------------------
    # Exact-match accuracy
    #
    # For MATCHED ground truth:
    # correct only when:
    #   prediction = AUTO_MATCH
    #   AND selected activity = correct activity
    # ---------------------------------------------------------------

    exact_correct = 0
    exact_total = 0

    for truth in evaluated_truth:

        if truth.label_type != LabelType.MATCHED:
            continue

        exact_total += 1

        prediction = prediction_by_report.get(
            truth.report_id
        )

        if prediction is None:
            continue

        if (
            prediction.decision
            == DecisionType.AUTO_MATCH
            and prediction.selected_activity_id
            == truth.correct_activity_id
        ):
            exact_correct += 1

    if exact_total > 0:

        exact_match_accuracy = _safe_metric(
            exact_correct / exact_total
        )

    else:

        exact_match_accuracy = None

    # ---------------------------------------------------------------
    # AUTO_MATCH accuracy
    #
    # Among all AUTO_MATCH predictions, determine how many
    # selected the correct activity.
    # ---------------------------------------------------------------

    auto_predictions = [
        prediction
        for prediction in prediction_records
        if prediction.decision
        == DecisionType.AUTO_MATCH
    ]

    auto_correct = 0

    for prediction in auto_predictions:

        truth = truth_by_report.get(
            prediction.report_id
        )

        if truth is None:
            continue

        if (
            truth.label_type
            == LabelType.MATCHED
            and prediction.selected_activity_id
            == truth.correct_activity_id
        ):
            auto_correct += 1

    if auto_predictions:

        auto_match_accuracy = _safe_metric(
            auto_correct / len(auto_predictions)
        )

    else:

        auto_match_accuracy = None

    # ---------------------------------------------------------------
    # HUMAN_REVIEW rate
    # ---------------------------------------------------------------

    human_review_count = sum(
        prediction.decision
        == DecisionType.HUMAN_REVIEW
        for prediction in prediction_records
    )

    if prediction_records:

        human_review_rate = _safe_metric(
            human_review_count
            / len(prediction_records)
        )

    else:

        human_review_rate = None

    # ---------------------------------------------------------------
    # UNMATCHED precision / recall / F1
    # ---------------------------------------------------------------

    y_true_unmatched = []
    y_pred_unmatched = []

    for truth in truth_records:

        prediction = prediction_by_report.get(
            truth.report_id
        )

        if prediction is None:
            continue

        actual_unmatched = (
            truth.label_type
            == LabelType.UNMATCHED
        )

        predicted_unmatched = (
            prediction.decision
            == DecisionType.UNMATCHED
        )

        y_true_unmatched.append(
            actual_unmatched
        )

        y_pred_unmatched.append(
            predicted_unmatched
        )

    if y_true_unmatched:

        precision, recall, f1, _ = (
            precision_recall_fscore_support(
                y_true_unmatched,
                y_pred_unmatched,
                pos_label=True,
                average="binary",
                zero_division=0,
            )
        )

        unmatched_metrics = {
            "precision": _safe_metric(precision),
            "recall": _safe_metric(recall),
            "f1": _safe_metric(f1),
        }

    else:

        unmatched_metrics = {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }

    # ---------------------------------------------------------------
    # Confusion matrix
    # ---------------------------------------------------------------

    confusion_counts = {}

    for truth in truth_records:

        prediction = prediction_by_report.get(
            truth.report_id
        )

        if prediction is None:
            continue

        actual = truth.label_type.value
        predicted = prediction.decision.value

        key = (
            predicted,
            actual
        )

        confusion_counts[key] = (
            confusion_counts.get(key, 0)
            + 1
        )

    confusion_matrix = [
        {
            "predicted": predicted,
            "actual": actual,
            "count": count,
        }
        for (
            predicted,
            actual
        ), count in sorted(
            confusion_counts.items()
        )
    ]

    # ---------------------------------------------------------------
    # Category-wise metrics
    # ---------------------------------------------------------------

    categories = [
        LabelType.MATCHED.value,
        LabelType.AMBIGUOUS.value,
        LabelType.UNMATCHED.value,
    ]

    category_metrics = []

    for category in categories:

        category_truth = []
        category_prediction = []

        for truth in truth_records:

            prediction = prediction_by_report.get(
                truth.report_id
            )

            if prediction is None:
                continue

            category_truth.append(
                truth.label_type.value
                == category
            )

            category_prediction.append(
                prediction.decision.value
                == category
            )

        count = sum(
            truth.label_type.value
            == category
            for truth in truth_records
        )

        if category_truth:

            precision, recall, f1, _ = (
                precision_recall_fscore_support(
                    category_truth,
                    category_prediction,
                    pos_label=True,
                    average="binary",
                    zero_division=0,
                )
            )

            correct = sum(
                actual == predicted
                for actual, predicted
                in zip(
                    category_truth,
                    category_prediction,
                )
            )

            accuracy = (
                correct / len(category_truth)
            )

            category_metrics.append(
                {
                    "category": category,
                    "count": count,
                    "accuracy": _safe_metric(
                        accuracy
                    ),
                    "precision": _safe_metric(
                        precision
                    ),
                    "recall": _safe_metric(
                        recall
                    ),
                    "f1": _safe_metric(
                        f1
                    ),
                }
            )

        else:

            category_metrics.append(
                {
                    "category": category,
                    "count": count,
                    "accuracy": None,
                    "precision": None,
                    "recall": None,
                    "f1": None,
                }
            )

    # ---------------------------------------------------------------
    # Misclassified examples
    # ---------------------------------------------------------------

    misclassified_examples = []

    for truth in truth_records:

        prediction = prediction_by_report.get(
            truth.report_id
        )

        # No prediction available.
        if prediction is None:

            misclassified_examples.append(
                truth.report_id
            )

            continue

        correct = False

        # MATCHED ground truth
        if truth.label_type == LabelType.MATCHED:

            correct = (
                prediction.decision
                == DecisionType.AUTO_MATCH
                and prediction.selected_activity_id
                == truth.correct_activity_id
            )

        # UNMATCHED ground truth
        elif truth.label_type == LabelType.UNMATCHED:

            correct = (
                prediction.decision
                == DecisionType.UNMATCHED
            )

        # AMBIGUOUS ground truth
        elif truth.label_type == LabelType.AMBIGUOUS:

            correct = (
                prediction.decision
                == DecisionType.HUMAN_REVIEW
            )

        if not correct:

            misclassified_examples.append(
                truth.report_id
            )

    # ---------------------------------------------------------------
    # Final result
    # ---------------------------------------------------------------

    result = {
        "total_reports": total_reports,
        "evaluated_reports": evaluated_reports,
        "excluded_ambiguous": (
            excluded_ambiguous
            if exclude_ambiguous
            else 0
        ),
        "exact_match_accuracy":
            exact_match_accuracy,
        "auto_match_accuracy":
            auto_match_accuracy,
        "human_review_rate":
            human_review_rate,
        "unmatched_metrics":
            unmatched_metrics,
        "confusion_matrix":
            confusion_matrix,
        "category_metrics":
            category_metrics,
        "misclassified_examples":
            misclassified_examples,
    }

    # ---------------------------------------------------------------
    # Required inline validation
    # ---------------------------------------------------------------

    return EvaluationResult(**result)


# ===================================================================
# MANUAL CHECK
# ===================================================================

if __name__ == "__main__":

    # Project root:
    # SIH2026-122/
    #
    # Ground truth:
    # SIH2026-122/Data/ground_truth_v1.csv

    ground_truth_path = (
        "Data/ground_truth_v1.csv"
    )

    ground_truth_df = pd.read_csv(
        ground_truth_path
    )

    # ---------------------------------------------------------------
    # Build a few hand-built DecisionResult fixtures
    # ---------------------------------------------------------------

    predictions = []

    for index, row in (
        ground_truth_df.head(5).iterrows()
    ):

        report_id = str(
            row["report_id"]
        )

        label = str(
            row["label_type"]
        )

        # -----------------------------------------------------------
        # MATCHED
        # -----------------------------------------------------------

        if label == LabelType.MATCHED.value:

            # Correct AUTO_MATCH
            if index % 2 == 0:

                predictions.append(
                    DecisionResult(
                        report_id=report_id,
                        decision=DecisionType.AUTO_MATCH,
                        selected_activity_id=str(
                            row[
                                "correct_activity_id"
                            ]
                        ),
                        confidence=0.95,
                        best_score=0.95,
                        decision_reasons=[
                            "Correct manual fixture"
                        ],
                    )
                )

            # Incorrect AUTO_MATCH
            else:

                predictions.append(
                    DecisionResult(
                        report_id=report_id,
                        decision=DecisionType.AUTO_MATCH,
                        selected_activity_id=(
                            "WRONG_ACTIVITY"
                        ),
                        confidence=0.80,
                        best_score=0.80,
                        decision_reasons=[
                            "Intentional incorrect fixture"
                        ],
                    )
                )

        # -----------------------------------------------------------
        # UNMATCHED
        # -----------------------------------------------------------

        elif label == LabelType.UNMATCHED.value:

            predictions.append(
                DecisionResult(
                    report_id=report_id,
                    decision=DecisionType.UNMATCHED,
                    selected_activity_id=None,
                    confidence=0.90,
                    decision_reasons=[
                        "Unmatched manual fixture"
                    ],
                )
            )

        # -----------------------------------------------------------
        # AMBIGUOUS
        # -----------------------------------------------------------

        else:

            predictions.append(
                DecisionResult(
                    report_id=report_id,
                    decision=DecisionType.HUMAN_REVIEW,
                    selected_activity_id=None,
                    confidence=0.50,
                    decision_reasons=[
                        "Ambiguous manual fixture"
                    ],
                )
            )

    # ---------------------------------------------------------------
    # Run evaluation
    # ---------------------------------------------------------------

    result = evaluate_predictions(
        predictions=predictions,
        ground_truth=ground_truth_df,
        config={
            "exclude_ambiguous": True
        },
    )

    # ---------------------------------------------------------------
    # Display results
    # ---------------------------------------------------------------

    print(
        "\n===== MODULE 7 EVALUATION ====="
    )

    print(
        "Total reports:",
        result.total_reports
    )

    print(
        "Evaluated reports:",
        result.evaluated_reports
    )

    print(
        "Excluded ambiguous:",
        result.excluded_ambiguous
    )

    print(
        "Exact-match accuracy:",
        result.exact_match_accuracy
    )

    print(
        "AUTO_MATCH accuracy:",
        result.auto_match_accuracy
    )

    print(
        "HUMAN_REVIEW rate:",
        result.human_review_rate
    )

    print(
        "UNMATCHED metrics:",
        result.unmatched_metrics
    )

    print(
        "Confusion matrix:",
        result.confusion_matrix
    )

    print(
        "Category metrics:",
        result.category_metrics
    )

    print(
        "Misclassified examples:",
        result.misclassified_examples
    )

    print(
        "\n✓ EvaluationResult validation passed"
    )