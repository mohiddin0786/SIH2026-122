import csv

from shared.schemas import RawReportInput
from shared.constants import DecisionType
from integration.pipeline import Pipeline
from Engine.module_1_normalization.normalizer import normalize_report
from Engine.module_2_extraction.extractor import extract_information
from Engine.module_4_matching.ranker import rank_candidates

# The FAMR ceiling you're willing to accept in production. Configs above
# this are excluded from consideration entirely, not just penalized.
MAX_ACCEPTABLE_FAMR = 0.05  # 5% -- adjust to whatever your team decides is safe


def tune_thresholds():
    # Load ground truth labels
    gt_map = {}
    with open("Data/ground_truth_v1.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gt_map[row["report_id"]] = row

    # Load all raw reports
    reports = []
    with open("Data/raw_reports_v1.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            reports.append(RawReportInput(
                report_id=row["report_id"],
                report_date=row["report_date"],
                source_type=row["source_type"],
                raw_text=row["raw_text"],
            ))

    print("Running pipeline to collect raw ranking scores...")
    pipeline = Pipeline()

    # NOTE: this does not pass report_date into rank_candidates(), matching
    # the current (unpatched) integration/pipeline.py. If/when report_date
    # gets wired in there, re-run this whole script -- score_gap values will
    # shift and any config picked before that fix is stale.
    scoring_data = []
    for raw in reports:
        normalized = normalize_report(raw)
        extracted = extract_information(normalized)
        candidates = pipeline._retrieve_fn(extracted, pipeline.schedule_index, top_k=5)
        ranking = rank_candidates(extracted, candidates)

        best_score = 0.0
        score_gap = 1.0
        best_activity = None

        if ranking.ranked_candidates:
            best_score = ranking.ranked_candidates[0].scores.final_score
            best_activity = ranking.ranked_candidates[0].activity_id
            if len(ranking.ranked_candidates) > 1:
                score_gap = best_score - ranking.ranked_candidates[1].scores.final_score

        gt_row = gt_map[raw.report_id]
        label_type = gt_row["label_type"]
        is_correct_match = (
            best_activity == gt_row.get("correct_activity_id")
        ) if label_type == "MATCHED" else False

        scoring_data.append({
            "report_id": raw.report_id,
            "best_score": best_score,
            "score_gap": score_gap,
            "label_type": label_type,
            "is_correct_match": is_correct_match,
        })

    print(f"Collected scores for {len(scoring_data)} reports.\n")
    print(f"Searching for max auto-match volume with FAMR <= {MAX_ACCEPTABLE_FAMR:.1%}...\n")

    # Grid search. rev_thresh range widened downward to cover the values
    # this pipeline has actually used/tuned to (0.20-0.30), plus some
    # exploration either side -- the previous 0.40-0.70 range never
    # overlapped real operating values and risked silently re-dropping
    # valid low-score reports without any metric catching it.
    auto_thresholds = [0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.92, 0.95]
    gap_thresholds = [0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
    review_thresholds = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

    results = []

    for auto_thresh in auto_thresholds:
        for gap_thresh in gap_thresholds:
            for rev_thresh in review_thresholds:

                tp = 0
                fp = 0
                human_review = 0
                unmatched_correctly_rejected = 0
                unmatched_wrongly_dropped = 0  # valid/ambiguous report lost -- a miss

                for d in scoring_data:
                    is_auto = (d["best_score"] >= auto_thresh and d["score_gap"] >= gap_thresh)
                    is_review = (d["best_score"] >= rev_thresh and not is_auto)

                    if is_auto:
                        if d["label_type"] == "MATCHED" and d["is_correct_match"]:
                            tp += 1
                        else:
                            fp += 1
                    elif is_review:
                        human_review += 1
                    else:
                        # UNMATCHED bucket -- split by whether ground truth
                        # agrees (genuinely UNMATCHED) or we lost a real one.
                        if d["label_type"] == "UNMATCHED":
                            unmatched_correctly_rejected += 1
                        else:
                            unmatched_wrongly_dropped += 1

                total_auto = tp + fp
                famr = (fp / total_auto) if total_auto > 0 else 0.0

                results.append({
                    "auto_thresh": auto_thresh,
                    "gap_thresh": gap_thresh,
                    "rev_thresh": rev_thresh,
                    "tp": tp,
                    "fp": fp,
                    "total_auto": total_auto,
                    "famr": famr,
                    "human_review": human_review,
                    "unmatched_correctly_rejected": unmatched_correctly_rejected,
                    "unmatched_wrongly_dropped": unmatched_wrongly_dropped,
                })

    # Only consider configs that meet the FAMR ceiling AND don't regress
    # wrongly-dropped valid reports back up. Among those, maximize volume.
    baseline_wrongly_dropped = min(r["unmatched_wrongly_dropped"] for r in results)
    eligible = [
        r for r in results
        if r["famr"] <= MAX_ACCEPTABLE_FAMR
        and r["unmatched_wrongly_dropped"] <= baseline_wrongly_dropped + 2  # small slack
    ]

    if not eligible:
        print(f"No config met FAMR <= {MAX_ACCEPTABLE_FAMR:.1%} with wrongly-dropped "
              f"near the achievable minimum ({baseline_wrongly_dropped}). "
              f"Showing the lowest-FAMR configs found instead:\n")
        eligible = sorted(results, key=lambda r: r["famr"])[:10]
    else:
        eligible.sort(key=lambda r: (-r["total_auto"], r["famr"]))

    print("=== TOP CANDIDATE CONFIGS (sorted by volume, within FAMR ceiling) ===")
    print(f"{'AUTO':>6} {'GAP':>6} {'REV':>6} {'AutoVol':>8} {'FAMR':>7} "
          f"{'Review':>7} {'UnmCorrect':>11} {'UnmWrong':>9}")
    for r in eligible[:15]:
        print(f"{r['auto_thresh']:>6.2f} {r['gap_thresh']:>6.2f} {r['rev_thresh']:>6.2f} "
              f"{r['total_auto']:>8} {r['famr']:>6.2%} "
              f"{r['human_review']:>7} {r['unmatched_correctly_rejected']:>11} "
              f"{r['unmatched_wrongly_dropped']:>9}")

    best = eligible[0]
    print("\n=== RECOMMENDED CONFIG ===")
    print(f"AUTO_MATCH_THRESHOLD = {best['auto_thresh']:.2f}")
    print(f"MIN_SCORE_GAP        = {best['gap_thresh']:.2f}")
    print(f"REVIEW_THRESHOLD     = {best['rev_thresh']:.2f}")
    print("-" * 40)
    print(f"Auto-match volume:          {best['total_auto']} ({best['total_auto']/len(scoring_data):.1%})")
    print(f"FAMR:                       {best['famr']:.2%}")
    print(f"Human review:               {best['human_review']}")
    print(f"Unmatched (correct reject): {best['unmatched_correctly_rejected']}")
    print(f"Unmatched (wrongly dropped):{best['unmatched_wrongly_dropped']}")


if __name__ == '__main__':
    tune_thresholds()