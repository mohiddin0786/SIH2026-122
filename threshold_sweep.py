"""
threshold_sweep.py — Run matching ONCE, then sweep many decision-threshold
combinations instantly against cached scores, reporting FAMR / volume /
unmatched-wrong for each. This decouples the expensive part (extraction +
retrieval + ranking) from the cheap part (the three-threshold decision
rule), so you can explore the trade-off space in seconds instead of
re-running the full pipeline for every combo.

Usage:
    python threshold_sweep.py

Then read the printed table and pick the row that best balances:
  - FAMR (lower is safer)
  - auto_match volume (higher is more automation)
  - unmatched_wrong (lower means fewer valid/ambiguous reports lost)
"""

import csv

from shared.schemas import RawReportInput
from integration.pipeline import Pipeline


def collect_scores():
    """Run the full pipeline once per report, but only keep what the
    decision rule needs: best_score, second_best_score, and ground truth.
    Everything else (extraction, matching detail) is discarded to keep
    this cheap to hold in memory."""
    ground_truth = []
    with open("Data/ground_truth_v1.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ground_truth.append(row)
    gt_map = {row["report_id"]: row for row in ground_truth}

    reports = []
    with open("Data/raw_reports_v1.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            reports.append(
                RawReportInput(
                    report_id=row["report_id"],
                    report_date=row["report_date"],
                    source_type=row["source_type"],
                    raw_text=row["raw_text"],
                )
            )

    print(f"Running matching for {len(reports)} reports (one-time cost)...")
    pipeline = Pipeline()

    cache = []  # list of dicts: report_id, label_type, correct_activity_id, best_id, best_score, second_score
    for raw in reports:
        result = pipeline.process_report(raw, ground_truth=None)  # skip Module 7 eval, we do our own
        if result.failed() or result.ranking is None or not result.ranking.ranked_candidates:
            cache.append({
                "report_id": raw.report_id,
                "label_type": (gt_map.get(raw.report_id) or {}).get("label_type", "").strip().upper(),
                "correct_activity_id": (gt_map.get(raw.report_id) or {}).get("correct_activity_id") or None,
                "best_id": None,
                "best_score": None,
                "second_score": None,
            })
            continue

        ranked = result.ranking.ranked_candidates
        best = ranked[0]
        second_score = ranked[1].scores.final_score if len(ranked) > 1 else None

        gt = gt_map.get(raw.report_id) or {}
        cache.append({
            "report_id": raw.report_id,
            "label_type": gt.get("label_type", "").strip().upper(),
            "correct_activity_id": gt.get("correct_activity_id") or None,
            "best_id": best.activity_id,
            "best_score": best.scores.final_score,
            "second_score": second_score,
        })

    print(f"Done. Cached scores for {len(cache)} reports.\n")
    return cache


def evaluate_thresholds(cache, auto_threshold, min_gap, review_threshold):
    """Apply the decision rule locally (mirrors decision.py's logic)
    against cached scores -- no pipeline re-run needed."""
    auto_correct = auto_wrong = 0
    review_by_label = {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0, "OTHER": 0}
    unmatched_correct = unmatched_wrong = 0
    no_candidates = 0

    for row in cache:
        if row["best_score"] is None:
            no_candidates += 1
            # No candidates at all -> UNMATCHED
            if row["label_type"] == "UNMATCHED":
                unmatched_correct += 1
            else:
                unmatched_wrong += 1
            continue

        best_score = row["best_score"]
        second_score = row["second_score"]
        gap = (best_score - second_score) if second_score is not None else None

        if best_score >= auto_threshold and (gap is None or gap >= min_gap):
            is_correct = (
                row["label_type"] == "MATCHED"
                and row["correct_activity_id"] is not None
                and row["best_id"] == row["correct_activity_id"]
            )
            if is_correct:
                auto_correct += 1
            else:
                auto_wrong += 1
        elif best_score >= review_threshold:
            label = row["label_type"] if row["label_type"] in review_by_label else "OTHER"
            review_by_label[label] += 1
        else:
            if row["label_type"] == "UNMATCHED":
                unmatched_correct += 1
            else:
                unmatched_wrong += 1

    total_auto = auto_correct + auto_wrong
    total_review = sum(review_by_label.values())
    total_unmatched = unmatched_correct + unmatched_wrong
    famr = (auto_wrong / total_auto * 100) if total_auto else 0.0

    return {
        "auto_total": total_auto,
        "auto_correct": auto_correct,
        "auto_wrong": auto_wrong,
        "famr": famr,
        "review_total": total_review,
        "review_matched": review_by_label["MATCHED"],
        "unmatched_total": total_unmatched,
        "unmatched_wrong": unmatched_wrong,
    }


def main():
    cache = collect_scores()

    # Sweep grid -- adjust ranges here if you want finer/coarser search.
    auto_thresholds = [0.60, 0.65, 0.70, 0.75, 0.80]
    min_gaps = [0.02, 0.05, 0.08]
    review_thresholds = [0.20, 0.25, 0.30, 0.35]

    results = []
    for auto_t in auto_thresholds:
        for gap_t in min_gaps:
            for rev_t in review_thresholds:
                if rev_t >= auto_t:
                    continue  # nonsensical: review floor must be below auto ceiling
                r = evaluate_thresholds(cache, auto_t, gap_t, rev_t)
                r["auto_threshold"] = auto_t
                r["min_gap"] = gap_t
                r["review_threshold"] = rev_t
                results.append(r)

    # Sort candidates: prioritize low FAMR (<=8% cutoff), then maximize
    # auto_total, then minimize unmatched_wrong.
    acceptable = [r for r in results if r["famr"] <= 8.0]
    acceptable.sort(key=lambda r: (-r["auto_total"], r["unmatched_wrong"]))

    print("=" * 100)
    print("TOP 15 CONFIGS (FAMR <= 8%, sorted by auto-match volume desc, then unmatched_wrong asc)")
    print("=" * 100)
    header = f"{'AUTO':<6}{'GAP':<6}{'REV':<6}{'AutoVol':<9}{'FAMR%':<8}{'Review':<8}{'RevMATCHED':<12}{'Unmatch':<9}{'UnmWrong':<9}"
    print(header)
    for r in acceptable[:15]:
        print(
            f"{r['auto_threshold']:<6}{r['min_gap']:<6}{r['review_threshold']:<6}"
            f"{r['auto_total']:<9}{r['famr']:<8.2f}{r['review_total']:<8}{r['review_matched']:<12}"
            f"{r['unmatched_total']:<9}{r['unmatched_wrong']:<9}"
        )

    print("\n" + "=" * 100)
    print("For reference -- your ORIGINAL true baseline (weights only, no threshold tuning):")
    print("  AUTO=0.85 GAP=0.10 REV=0.60 -> auto_vol=407, FAMR=6.63%, unmatched_wrong=30")
    print("=" * 100)


if __name__ == "__main__":
    main()