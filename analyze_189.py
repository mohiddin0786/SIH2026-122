"""
diagnose_root_cause.py — Separates failures by WHICH module actually
caused them, so you stop tuning Module 4/5 for problems that live
upstream. No amount of scoring/threshold tuning in Module 4/5 can recover
a report whose correct answer was never retrieved by Module 3 in the
first place -- that's a hard ceiling, not a tuning problem.

THREE INDEPENDENT CHECKS:

  A) CANDIDATE RECALL (Module 3 ceiling check)
     For every MATCHED ground-truth report: is correct_activity_id
     present ANYWHERE in the top-K candidates returned by Module 3?
     If recall < ~95%, Module 3's retrieval (equipment/location/activity
     fuzzy matching + semantic backend, or top_k itself) is the real
     bottleneck -- Module 4/5 literally cannot fix these regardless of
     any scoring/threshold change, because the right answer was never
     handed to them.

  B) EXTRACTION COMPLETENESS (Module 1/2 ceiling check)
     For every report, did Module 2 extract SOMETHING for equipment_tag /
     location / activity_type? A report with zero extracted signals can
     only ever be matched on semantic text similarity alone -- which is
     exactly the weak, tie-prone signal you've been fighting all session.
     High rates of "nothing extracted" point at Module 2's extraction
     prompt/logic, not Module 4's scoring weights.

  C) EXTRACTION CORRECTNESS (spot-check, Module 2 quality)
     For reports where the correct candidate's equipment_tag is known
     (from schedule_master), does the report's EXTRACTED equipment tag
     actually match it? A mismatch here (report clearly mentions "SP-101"
     but extraction returned something else, or nothing) is a Module 2
     bug independent of anything in Module 3/4/5.
"""

import csv


from shared.schemas import RawReportInput
from integration.pipeline import Pipeline
from Engine.module_6_schedule_update.config import ScheduleUpdateConfig
from Engine.module_6_schedule_update.repository import ExecutionStateRepository

# Same reasoning as run_benchmark.py — keep diagnostic runs out of the live
# execution_state.csv that python_backend reads for the demo.
_DIAG_CONFIG = ScheduleUpdateConfig(execution_state_path="Data/execution_state_benchmark.csv")
_DIAG_REPOSITORY = ExecutionStateRepository(_DIAG_CONFIG)




def main():
    ground_truth = []
    with open("Data/ground_truth_v1.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ground_truth.append(row)
    gt_map = {row["report_id"]: row for row in ground_truth}

    schedule_by_id = {}
    with open("Data/schedule_master_v1.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            schedule_by_id[row["activity_id"]] = row

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

    print(f"Processing {len(reports)} reports for root-cause diagnosis...")
    pipeline = Pipeline()

    # --- A) Candidate recall ---
    matched_total = 0
    matched_recalled = 0
    recall_misses = []  # report_ids where correct answer wasn't even retrieved

    # --- B) Extraction completeness ---
    no_equipment = 0
    no_location = 0
    unknown_activity = 0

    # --- C) Extraction correctness (equipment tag) ---
    equip_checkable = 0
    equip_correct = 0
    equip_mismatches = []

    for raw in reports:
        result = pipeline.process_report(raw, ground_truth=None)
        if result.failed():
            continue

        extracted = result.extracted_report
        gt = gt_map.get(raw.report_id) or {}
        label = gt.get("label_type", "").strip().upper()
        correct_id = (gt.get("correct_activity_id") or "").strip() or None

        # --- B) completeness, tracked for ALL reports ---
        if not extracted.equipment_tags:
            no_equipment += 1
        if not extracted.locations:
            no_location += 1
        if extracted.activity_type.value is None or str(extracted.activity_type.value) == "UNKNOWN":
            unknown_activity += 1

        # --- A) candidate recall, only meaningful for MATCHED reports ---
        if label == "MATCHED" and correct_id:
            matched_total += 1
            candidate_ids = {c.activity_id for c in result.candidates.candidates} if result.candidates else set()
            if correct_id in candidate_ids:
                matched_recalled += 1
            else:
                recall_misses.append((raw.report_id, correct_id, raw.raw_text[:80]))

            # --- C) extraction correctness vs schedule's true equipment tag ---
            sched_row = schedule_by_id.get(correct_id)
            true_equip_tag = (sched_row or {}).get("equipment_tag", "").strip() or None
            if true_equip_tag:
                equip_checkable += 1
                extracted_tags = [e.value.strip().upper().replace(" ", "").replace("-", "") for e in extracted.equipment_tags]
                normalized_true = true_equip_tag.strip().upper().replace(" ", "").replace("-", "")
                if normalized_true in extracted_tags:
                    equip_correct += 1
                else:
                    equip_mismatches.append((
                        raw.report_id,
                        true_equip_tag,
                        [e.value for e in extracted.equipment_tags],
                        raw.raw_text[:80],
                    ))

    print("\n" + "=" * 90)
    print("A) CANDIDATE RECALL (Module 3 ceiling check)")
    print("=" * 90)
    recall_pct = (matched_recalled / matched_total * 100) if matched_total else 0.0
    print(f"MATCHED reports where correct_activity_id was retrieved by Module 3: "
          f"{matched_recalled} / {matched_total} ({recall_pct:.1f}%)")
    if recall_pct < 95.0:
        print("  >>> RECALL GAP DETECTED. These reports can NEVER be auto-matched or even")
        print("      correctly reviewed, no matter how Module 4/5 is tuned. Fix Module 3 first.")
    print(f"\nFirst 15 recall misses (correct answer never made it into candidates):")
    for rid, cid, text in recall_misses[:15]:
        print(f"  {rid:<12} correct_id={cid:<10} text: {text}")

    print("\n" + "=" * 90)
    print("B) EXTRACTION COMPLETENESS (Module 1/2 signal availability)")
    print("=" * 90)
    total = len(reports)
    print(f"Reports with NO equipment tag extracted: {no_equipment} / {total} ({100*no_equipment/total:.1f}%)")
    print(f"Reports with NO location extracted:      {no_location} / {total} ({100*no_location/total:.1f}%)")
    print(f"Reports with UNKNOWN activity_type:       {unknown_activity} / {total} ({100*unknown_activity/total:.1f}%)")

    print("\n" + "=" * 90)
    print("C) EXTRACTION CORRECTNESS (equipment tag, for MATCHED reports with a known true tag)")
    print("=" * 90)
    equip_acc = (equip_correct / equip_checkable * 100) if equip_checkable else 0.0
    print(f"Correct equipment tag actually extracted: {equip_correct} / {equip_checkable} ({equip_acc:.1f}%)")
    print(f"\nFirst 15 equipment extraction mismatches:")
    for rid, true_tag, extracted_tags, text in equip_mismatches[:15]:
        print(f"  {rid:<12} true_tag={true_tag:<10} extracted={extracted_tags}")
        print(f"      text: {text}")

    print("\n" + "=" * 90)
    print("VERDICT")
    print("=" * 90)
    if recall_pct < 95.0:
        print(f"-> Module 3 (retrieval) is losing {matched_total - matched_recalled} correct answers before")
        print(f"   Module 4 ever sees them. This is likely your biggest lever, bigger than any")
        print(f"   Module 4/5 threshold tuning.")
    if equip_acc < 90.0 and equip_checkable > 0:
        print(f"-> Module 2 (extraction) is misreading/missing equipment tags in "
              f"{equip_checkable - equip_correct} reports. Since equipment_tag carries the")
        print(f"   highest weight in Module 4's scoring, this directly caps match quality.")
    if recall_pct >= 95.0 and equip_acc >= 90.0:
        print("-> Module 3 recall and Module 2 equipment extraction both look healthy.")
        print("   The remaining gap is genuinely in Module 4/5 scoring/thresholds -- and you've")
        print("   already tuned that space fairly thoroughly this session.")


if __name__ == "__main__":
    main()