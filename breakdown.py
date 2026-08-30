import csv
from shared.schemas import RawReportInput
from integration.pipeline import Pipeline
from Engine.module_4_matching.config import MatchingConfig

def print_breakdown():
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
            
    pipeline = Pipeline()
    
    # Thresholds we are using
    AUTO_THRESH = 0.80
    GAP_THRESH = 0.02
    REV_THRESH = 0.30
    
    # Counters
    # mapping structure: decision -> ground_truth_label -> count
    breakdown = {
        "HUMAN_REVIEW": {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0},
        "UNMATCHED": {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0}
    }
    
    for raw in reports:
        normalized = __import__('Engine.module_1_normalization.normalizer').module_1_normalization.normalizer.normalize_report(raw)
        extracted = __import__('Engine.module_2_extraction.extractor').module_2_extraction.extractor.extract_information(normalized)
        candidates = pipeline._retrieve_fn(extracted, pipeline.schedule_index, top_k=5)
        ranking = __import__('Engine.module_4_matching.ranker').module_4_matching.ranker.rank_candidates(extracted, candidates)
        
        best_score = 0.0
        score_gap = 1.0
        if ranking.ranked_candidates:
            best_score = ranking.ranked_candidates[0].scores.final_score
            if len(ranking.ranked_candidates) > 1:
                score_gap = best_score - ranking.ranked_candidates[1].scores.final_score
                
        is_auto = (best_score >= AUTO_THRESH and score_gap >= GAP_THRESH)
        is_review = (best_score >= REV_THRESH and not is_auto)
        
        gt_label = gt_map[raw.report_id]["label_type"]
        
        if not is_auto:
            decision = "HUMAN_REVIEW" if is_review else "UNMATCHED"
            breakdown[decision][gt_label] += 1
            
    print("=== BREAKDOWN OF NON-AUTO MATCHED REPORTS ===")
    print(f"Total Sent to HUMAN_REVIEW: {sum(breakdown['HUMAN_REVIEW'].values())}")
    for label, count in breakdown['HUMAN_REVIEW'].items():
        print(f"  - Originally labeled '{label}': {count}")
        
    print(f"\nTotal Rejected as UNMATCHED: {sum(breakdown['UNMATCHED'].values())}")
    for label, count in breakdown['UNMATCHED'].items():
        print(f"  - Originally labeled '{label}': {count}")

if __name__ == '__main__':
    print_breakdown()

