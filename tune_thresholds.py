import csv
from shared.schemas import RawReportInput
from integration.pipeline import Pipeline
from shared.constants import DecisionType

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
            
    print("Running pipeline to collect raw Ranking scores...")
    pipeline = Pipeline()
    
    # Store results: (report_id, best_score, score_gap, label_type, best_activity)
    scoring_data = []
    
    for raw in reports:
        # process up to Ranking
        normalized = pipeline.normalized_report = __import__('Engine.module_1_normalization.normalizer').module_1_normalization.normalizer.normalize_report(raw)
        extracted = __import__('Engine.module_2_extraction.extractor').module_2_extraction.extractor.extract_information(normalized)
        candidates = pipeline._retrieve_fn(extracted, pipeline.schedule_index, top_k=5)
        ranking = __import__('Engine.module_4_matching.ranker').module_4_matching.ranker.rank_candidates(extracted, candidates)
        
        best_score = 0.0
        score_gap = 1.0
        best_activity = None
        
        if ranking.ranked_candidates:
            best_score = ranking.ranked_candidates[0].scores.final_score
            best_activity = ranking.ranked_candidates[0].activity_id
            if len(ranking.ranked_candidates) > 1:
                score_gap = best_score - ranking.ranked_candidates[1].scores.final_score
                
        label_type = gt_map[raw.report_id]["label_type"]
        is_correct_match = (best_activity == gt_map[raw.report_id].get("correct_activity_id")) if label_type == "MATCHED" else False
        
        scoring_data.append({
            "report_id": raw.report_id,
            "best_score": best_score,
            "score_gap": score_gap,
            "label_type": label_type,
            "is_correct_match": is_correct_match
        })

    print(f"Collected scores for {len(scoring_data)} reports.")
    print("Testing threshold combinations...\n")
    
    # Grid Search
    best_config = None
    max_score = -9999
    
    for auto_thresh in [0.70, 0.75, 0.80, 0.85, 0.90, 0.92, 0.95]:
        for gap_thresh in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
            for rev_thresh in [0.40, 0.50, 0.60, 0.70]:
                
                # We want to maximize True Positives (Correct AUTO_MATCH)
                # and minimize False Positives (AUTO_MATCH on AMBIGUOUS/UNMATCHED or wrong activity)
                
                tp = 0
                fp = 0
                human_review = 0
                unmatched = 0
                
                for d in scoring_data:
                    is_auto = (d["best_score"] >= auto_thresh and d["score_gap"] >= gap_thresh)
                    is_review = (d["best_score"] >= rev_thresh and not is_auto)
                    
                    if is_auto:
                        # Auto match! Is it correct?
                        if d["label_type"] == "MATCHED" and d["is_correct_match"]:
                            tp += 1
                        else:
                            fp += 1
                    elif is_review:
                        human_review += 1
                    else:
                        unmatched += 1
                
                # Simple scoring metric: 
                # +1 for every correct auto-match
                # -5 for every false positive auto-match (high penalty for bad autonomous action)
                score = tp - (fp * 5)
                
                if score > max_score:
                    max_score = score
                    best_config = (auto_thresh, gap_thresh, rev_thresh, tp, fp, human_review, unmatched)
                    
    print("=== BEST THRESHOLDS FOUND ===")
    print(f"AUTO_MATCH_THRESHOLD = {best_config[0]:.2f}")
    print(f"MIN_SCORE_GAP      = {best_config[1]:.2f}")
    print(f"REVIEW_THRESHOLD   = {best_config[2]:.2f}")
    print("-" * 30)
    print(f"Correct Auto-Matches (True Positives):  {best_config[3]}")
    print(f"Incorrect Auto-Matches (False Pos):     {best_config[4]}")
    print(f"Routed to Human Review:                 {best_config[5]}")
    print(f"Unmatched (Rejected):                   {best_config[6]}")

if __name__ == '__main__':
    tune_thresholds()

