# Module 1 — Normalization

Rule-based normalization for noisy infrastructure field reports.

`normalize_report(report: RawReportInput) -> NormalizedReport` preserves `report_id` and the exact original `raw_text`, while normalizing only a working text copy. Current rules correct a small set of known typos, normalize common wording/abbreviations, expand Pump Area aliases, standardize equipment tags such as `sp101` / `F 101` to `SP-101` / `F-101`, and collapse accidental whitespace.

This module does **not** extract entities, classify event type, infer progress, or read/update the Schedule Master. When processing `Data/raw_reports_v1.csv`, only `report_id`, `report_date`, `source_type`, and `raw_text` are selected; evaluation labels are never read into `RawReportInput`.

## Install

From the repository root:

```bash
pip install -r Engine/module_1_normalization/requirements.txt
```

## Canonical example correctness gate

Run this from the repository root. It loads the official shared example, runs the normalizer, converts the result to a dict, and validates that dict again with the official `NormalizedReport` schema.

```bash
python - <<'PY'
import json
from pathlib import Path

from shared.schemas import RawReportInput, NormalizedReport
from Engine.module_1_normalization import normalize_report

payload = json.loads(Path("shared/examples/01_raw_report_input.json").read_text())
report = RawReportInput(**payload)
result = normalize_report(report)
NormalizedReport(**result.model_dump())
print(result.model_dump())
print("PASS: canonical example validates as NormalizedReport")
PY
```

## Full CSV smoke run

This deliberately selects only the four legitimate input columns. It reports aggregate pass/fail counts and does not assert per row.

```bash
python - <<'PY'
import pandas as pd

from shared.schemas import RawReportInput
from Engine.module_1_normalization import normalize_report

INPUT_COLUMNS = ["report_id", "report_date", "source_type", "raw_text"]
df = pd.read_csv("Data/raw_reports_v1.csv", usecols=INPUT_COLUMNS, keep_default_na=False)

passed = 0
failed = 0
for row in df.to_dict(orient="records"):
    try:
        normalize_report(RawReportInput(**row))
        passed += 1
    except Exception as exc:
        failed += 1
        print(f"FAIL {row['report_id']}: {exc}")

print(f"PASS={passed} FAIL={failed} TOTAL={len(df)}")
PY
```
