import csv
import time
from collections import defaultdict

from shared.schemas import RawReportInput
from integration.pipeline import Pipeline

def run_benchmark():
    print("="*60)
    print("SIH2K26 End-to-End Pipeline Benchmark")
    print("="*60)

    # 1. Load ground truth
    ground_truth = []
    with open("Data/ground_truth_v1.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ground_truth.append(row)
    
    # 2. Load all raw reports
    reports = []
    with open("Data/raw_reports_v1.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            reports.append(RawReportInput(
                report_id=row["report_id"],
                report_date=row["report_date"],
                source_type=row["source_type"],
                raw_text=row["raw_text"],
            ))
            
    print(f"Loaded {len(reports)} reports and {len(ground_truth)} ground truth records.")
    
    # Initialize pipeline
    print("Initializing pipeline (building index)...")
    start_init = time.perf_counter()
    pipeline = Pipeline()
    init_duration = time.perf_counter() - start_init
    print(f"Pipeline initialization took {init_duration:.3f} seconds.")

    # Process all reports and measure time
    print("\nProcessing reports...")
    total_time = 0.0
    latencies = []
    
    success_count = 0
    fail_count = 0
    
    # E2E Accuracy Tracking
    correct_matches = 0
    evaluated_reports = 0

    # Let's map ground truth by report_id for easy checking
    gt_map = {row["report_id"]: row for row in ground_truth}

    for raw in reports:
        start_report = time.perf_counter()
        
        # We pass ground_truth to evaluate in module 7
        result = pipeline.process_report(raw, ground_truth=ground_truth)
        
        duration = time.perf_counter() - start_report
        latencies.append(duration)
        total_time += duration
        
        if result.failed():
            fail_count += 1
        else:
            success_count += 1
            
        # Manually check end-to-end correctness if decision exists
        if result.decision and result.decision.selected_activity_id:
            gt_record = gt_map.get(raw.report_id)
            if gt_record and gt_record.get("correct_activity_id"):
                evaluated_reports += 1
                if result.decision.selected_activity_id == gt_record["correct_activity_id"]:
                    correct_matches += 1

    # Print Report
    print("\n" + "="*60)
    print("Benchmark Results")
    print("="*60)
    print(f"Total Reports: {len(reports)}")
    print(f"Successful:    {success_count}")
    print(f"Failed:        {fail_count}")
    
    # E2E Accuracy
    if evaluated_reports > 0:
        accuracy = (correct_matches / evaluated_reports) * 100
        print(f"\nEnd-to-End Accuracy:")
        print(f"Correct Activity Matches: {correct_matches} / {evaluated_reports} ({accuracy:.1f}%)")
        
        # Check module 7 evaluation summary from the last report (it might accumulate or just be per-report)
        # Actually module 7 evaluate_predictions takes the whole dataset, let's just use our manual calc.
    
    # Performance
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

if __name__ == '__main__':
    run_benchmark()
