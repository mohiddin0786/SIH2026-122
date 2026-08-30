"""
integration/__main__.py — CLI entry point for the SIH2K26 end-to-end pipeline.

Usage:
    python -m integration --report-id RPT-0001
    python -m integration --demo            # run the built-in demo
"""

from __future__ import annotations

import argparse
import csv
import sys

from shared.schemas import RawReportInput

from integration.pipeline import Pipeline


def _load_raw_report(report_id: str) -> RawReportInput:
    """Load a single raw report from Data/raw_reports_v1.csv by report_id."""
    with open("Data/raw_reports_v1.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["report_id"] == report_id:
                return RawReportInput(
                    report_id=row["report_id"],
                    report_date=row["report_date"],
                    source_type=row["source_type"],
                    raw_text=row["raw_text"],
                )
    raise ValueError(f"Report {report_id!r} not found in Data/raw_reports_v1.csv")


def _demo() -> None:
    """End-to-end demo using RPT-0001 from the actual dataset."""
    report_id = "RPT-0001"
    print(f"\n{'='*60}")
    print(f"SIH2K26 Pipeline Demo — {report_id}")
    print(f"{'='*60}\n")

    raw = _load_raw_report(report_id)
    print(f"Raw text: {raw.raw_text}\n")

    pipeline = Pipeline()
    result = pipeline.process_report(raw)

    summary = result.to_summary()
    for key, value in summary.items():
        if isinstance(value, list):
            print(f"{key}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value}")

    if result.failed():
        print("\n[WARN] Pipeline completed with errors.")
        sys.exit(1)
    else:
        print("\n[OK] Pipeline completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SIH2K26 End-to-End Pipeline")
    parser.add_argument("--report-id", help="Process a specific report ID")
    parser.add_argument("--demo", action="store_true", help="Run the built-in demo")
    args = parser.parse_args()

    if args.demo:
        _demo()
    elif args.report_id:
        raw = _load_raw_report(args.report_id)
        pipeline = Pipeline()
        result = pipeline.process_report(raw)
        print(result.to_summary())
    else:
        parser.print_help()
        print("\nUse --demo to run the built-in demo, or --report-id <ID> for a specific report.")


if __name__ == "__main__":
    main()
