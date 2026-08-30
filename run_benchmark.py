"""
run_benchmark_fixed.py — Fixed-denominator, FAMR-aware pipeline benchmark.

WHY THIS REPLACES THE OLD SCRIPT:
    The old benchmark only counted a report toward "accuracy" when
    result.decision.selected_activity_id was not None. But HUMAN_REVIEW
    decisions can ALSO carry a selected_activity_id (per DecisionResult's
    own contract docstring: "HUMAN_REVIEW -> selected_activity_id MAY hold
    the leading candidate, but is not confirmed"). That silently mixed
    AUTO_MATCH and HUMAN_REVIEW into one "accuracy" number, and the mix
    changes every time thresholds/weights change -- which is exactly why
    the old script's denominator moved between runs (614 -> 678 -> 660)
    and made "accuracy" incomparable across configs.

WHAT THIS SCRIPT DOES INSTEAD:
    - Denominator is ALWAYS len(reports) (738), every run, no exceptions.
    - Every report is bucketed by (decision.decision, ground truth label)
      into exactly one of 6 buckets below -- no report is silently dropped
      or double-counted.
    - Reports False Auto-Match Rate (FAMR) explicitly -- the metric that
      actually matters for a system that writes to the schedule -- not a
      single "accuracy" number.

BUCKETS (mutually exclusive, sum to len(reports)):
    auto_correct    : AUTO_MATCH, label_type=MATCHED, selected == correct_activity_id
    auto_wrong      : AUTO_MATCH, but selected != correct_activity_id, OR the
                       ground truth for this report was actually AMBIGUOUS/
                       UNMATCHED (i.e. it should never have been auto-matched
                       at all). This is the FAMR numerator.
    review          : HUMAN_REVIEW, regardless of whether its tentative
                       selected_activity_id happens to be right -- it did not
                       auto-commit, so it's "safe", not "correct". Broken down
                       by ground-truth label for diagnostics.
    unmatched_correct: UNMATCHED, label_type=UNMATCHED (correctly rejected noise)
    unmatched_wrong  : UNMATCHED, but label_type=MATCHED or AMBIGUOUS
                       (a valid/tricky report was dropped -- a miss, not a
                       false auto-match, but still worth tracking)
    failed          : pipeline raised an error for this report
"""

import csv
import time
from collections import defaultdict

from shared.schemas import RawReportInput
from integration.pipeline import Pipeline


def run_benchmark():
    print("=" * 60)
    print("SIH2K26 End-to-End Pipeline Benchmark (fixed-denominator)")
    print("=" * 60)

    ground_truth = []
    with open("Data/ground_truth_v1.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ground_truth.append(row)
    gt_map = {row["report_id"]: row for row in ground_truth}

    reports = []
    with open("Data/raw_reports_v1.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            reports.append(
                RawReportInput(
                    report_id=row["report_id"],
                    report_date=row["report_date"],
                    source_type=row["source_type"],
                    raw_text=row["raw_text"],
                )
            )

    print(f"Loaded {len(reports)} reports and {len(ground_truth)} ground truth records.")

    print("Initializing pipeline (building index)...")
    start_init = time.perf_counter()
    pipeline = Pipeline()
    init_duration = time.perf_counter() - start_init
    print(f"Pipeline initialization took {init_duration:.3f} seconds.")

    print("\nProcessing reports...")
    total_time = 0.0
    latencies = []

    # Fixed-denominator buckets -- every report lands in exactly one.
    auto_correct = 0
    auto_wrong = 0
    review_by_label = defaultdict(int)  # MATCHED / AMBIGUOUS / UNMATCHED / (missing GT)
    unmatched_correct = 0
    unmatched_wrong = 0
    failed = 0
    missing_gt = 0  # report_id had no ground truth row at all -- data issue, flag it

    for raw in reports:
        start_report = time.perf_counter()
        result = pipeline.process_report(raw, ground_truth=ground_truth)
        duration = time.perf_counter() - start_report
        latencies.append(duration)
        total_time += duration

        if result.failed():
            failed += 1
            continue

        gt_record = gt_map.get(raw.report_id)
        if gt_record is None:
            missing_gt += 1
            continue

        label = gt_record.get("label_type", "").strip().upper()
        correct_id = (gt_record.get("correct_activity_id") or "").strip() or None
        decision = result.decision

        if decision is None:
            failed += 1
            continue

        if decision.decision == "AUTO_MATCH":
            is_correct = (
                label == "MATCHED"
                and correct_id is not None
                and decision.selected_activity_id == correct_id
            )
            if is_correct:
                auto_correct += 1
            else:
                auto_wrong += 1

        elif decision.decision == "HUMAN_REVIEW":
            review_by_label[label or "UNKNOWN"] += 1

        elif decision.decision == "UNMATCHED":
            if label == "UNMATCHED":
                unmatched_correct += 1
            else:
                unmatched_wrong += 1

        else:
            # Unexpected decision value -- surface it, don't silently drop it.
            failed += 1

    total_reports = len(reports)
    total_auto = auto_correct + auto_wrong
    total_review = sum(review_by_label.values())
    total_unmatched = unmatched_correct + unmatched_wrong

    accounted = auto_correct + auto_wrong + total_review + unmatched_correct + unmatched_wrong + failed + missing_gt
    assert accounted == total_reports, (
        f"Bucket accounting mismatch: {accounted} != {total_reports}. "
        "Every report must land in exactly one bucket -- fix before trusting numbers."
    )

    print("\n" + "=" * 60)
    print("Benchmark Results (fixed denominator = total reports)")
    print("=" * 60)
    print(f"Total Reports:     {total_reports}")
    print(f"Pipeline Failures: {failed}")
    print(f"Missing GT rows:   {missing_gt}  (data issue if > 0 -- investigate)")

    print(f"\n--- AUTO_MATCH bucket ---")
    print(f"Total Auto-Matched:     {total_auto}  ({100*total_auto/total_reports:.1f}% of all reports)")
    print(f"  Correct:              {auto_correct}")
    print(f"  Wrong (false match):  {auto_wrong}")
    famr = (auto_wrong / total_auto * 100) if total_auto else 0.0
    print(f"  >>> FAMR (False Auto-Match Rate): {famr:.2f}%  <<<")

    print(f"\n--- HUMAN_REVIEW bucket ---")
    print(f"Total sent to review:  {total_review}  ({100*total_review/total_reports:.1f}% of all reports)")
    for label, count in sorted(review_by_label.items()):
        print(f"  {label:12s}: {count}")

    print(f"\n--- UNMATCHED bucket ---")
    print(f"Total Unmatched:       {total_unmatched}  ({100*total_unmatched/total_reports:.1f}% of all reports)")
    print(f"  Correctly rejected:  {unmatched_correct}  (ground truth was genuinely UNMATCHED)")
    print(f"  Wrongly dropped:     {unmatched_wrong}  (valid/ambiguous report lost -- a miss, not a false-match)")

    print(f"\n--- Summary table (copy this into your comparison doc) ---")
    print(f"{'Metric':<28} {'Value'}")
    print(f"{'-'*40}")
    print(f"{'Total reports':<28} {total_reports}")
    print(f"{'Auto-match volume':<28} {total_auto} ({100*total_auto/total_reports:.1f}%)")
    print(f"{'FAMR':<28} {famr:.2f}%")
    print(f"{'Human review volume':<28} {total_review} ({100*total_review/total_reports:.1f}%)")
    print(f"{'Unmatched volume':<28} {total_unmatched} ({100*total_unmatched/total_reports:.1f}%)")
    print(f"{'Missed valid/ambiguous':<28} {unmatched_wrong}")

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p90 = latencies[int(len(latencies) * 0.90)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
    avg = sum(latencies) / len(latencies) if latencies else 0.0

    print(f"\nLatency Statistics (per report):")
    print(f"  Average: {avg*1000:.2f} ms")
    print(f"  P50:     {p50*1000:.2f} ms")
    print(f"  P90:     {p90*1000:.2f} ms")
    print(f"  P99:     {p99*1000:.2f} ms")

    throughput = len(reports) / total_time if total_time > 0 else 0
    print(f"\nThroughput: {throughput:.2f} reports / second")


if __name__ == "__main__":
    run_benchmark()