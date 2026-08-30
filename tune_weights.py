import csv
from shared.schemas import RawReportInput
from integration.pipeline import Pipeline
from Engine.module_4_matching.config import MatchingConfig, MatchingWeights
from Engine.module_4_matching.ranker import rank_candidates

def tune_weights():
    # Load ground truth labels
    gt_map = {}
    with open("Data/ground_truth_v1.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gt_map[row["report_id"]] = row
            
    reports = []
    with open("Data/raw_reports_v1.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            reports.append(RawReportInput(
                report_id=row["report_id"],
                report_date=row["report_date"],
                source_type=row["source_type"],
                raw_text=row["raw_text"],
            ))
            
    print("Initializing pipeline (caching extracted & retrieved candidates)...")
    pipeline = Pipeline()
    
    # Pre-compute up to candidate retrieval for speed
    precomputed = []
    
    for raw in reports:
        normalized = __import__('Engine.module_1_normalization.normalizer').module_1_normalization.normalizer.normalize_report(raw)
        extracted = __import__('Engine.module_2_extraction.extractor').module_2_extraction.extractor.extract_information(normalized)
        candidates = pipeline._retrieve_fn(extracted, pipeline.schedule_index, top_k=5)
        
        label_type = gt_map[raw.report_id]["label_type"]
        correct_activity_id = gt_map[raw.report_id].get("correct_activity_id")
        
        precomputed.append((raw.report_id, extracted, candidates, label_type, correct_activity_id))

    print(f"Precomputed {len(precomputed)} reports. Testing weight combinations...\n")
    
    # Grid search over weights
    best_tp = -1
    best_weights = None
    
    # Generate weight combos (must sum to 1.0)
    combos = [
        (0.20, 0.30, 0.20, 0.15, 0.05, 0.10), # Current Default
        (0.15, 0.35, 0.20, 0.10, 0.05, 0.15), # High Equipment/Date
        (0.10, 0.40, 0.20, 0.10, 0.05, 0.15), # Massive Equipment bias
        (0.25, 0.25, 0.15, 0.15, 0.10, 0.10), # High Semantic
        (0.05, 0.40, 0.20, 0.20, 0.05, 0.10), # Minimal semantic
        (0.20, 0.30, 0.20, 0.10, 0.05, 0.15), # Higher date
    ]
    
    # Fix the decision thresholds to the "Aggressive" option we found earlier
    # to see how many auto matches we get with 0-15 errors.
    AUTO_THRESH = 0.80
    GAP_THRESH = 0.02
    REV_THRESH = 0.30
    
    for (sem, eq, act, loc, disc, date_wt) in combos:
        config = MatchingConfig(
            weights=MatchingWeights(
                semantic_weight=sem,
                equipment_weight=eq,
                activity_weight=act,
                location_weight=loc,
                discipline_weight=disc,
                date_weight=date_wt
            )
        )
        
        tp = 0
        fp = 0
        
        for (rid, ext, cands, label, correct_id) in precomputed:
            ranking = rank_candidates(ext, cands, config=config)
            if not ranking.ranked_candidates:
                continue
                
            best_score = ranking.ranked_candidates[0].scores.final_score
            best_id = ranking.ranked_candidates[0].activity_id
            score_gap = 1.0
            if len(ranking.ranked_candidates) > 1:
                score_gap = best_score - ranking.ranked_candidates[1].scores.final_score
                
            is_auto = (best_score >= AUTO_THRESH and score_gap >= GAP_THRESH)
            if is_auto:
                if label == "MATCHED" and best_id == correct_id:
                    tp += 1
                else:
                    fp += 1
                    
        print(f"Weights (Sem:{sem:.2f}, Eq:{eq:.2f}, Act:{act:.2f}, Loc:{loc:.2f}, Disc:{disc:.2f}, Date:{date_wt:.2f}) -> Auto-Matches: {tp}, Errors: {fp}")
        
        if fp <= 15 and tp > best_tp:
            best_tp = tp
            best_weights = (sem, eq, act, loc, disc, date_wt)
            
    print(f"\nBest Weights found (under 15 errors): {best_weights} with {best_tp} Auto-Matches!")

if __name__ == '__main__':
    tune_weights()

