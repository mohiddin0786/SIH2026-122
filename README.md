# SIH2026-122 — Automated Progress Report Matching & Schedule Update Engine

An end-to-end system that reads noisy, free-text field/DPR (Daily Progress Report) updates from a construction/industrial project, automatically figures out **which schedule activity each report is about**, and updates that activity's actual execution status — with a human-review safety net for anything the system isn't confident about.

The project has three parts that all speak the same contract:

- **Engine** — a 7-module Python pipeline that turns a raw report into a schedule update (and, offline, an accuracy evaluation).
- **backend** — a FastAPI service that exposes the pipeline and the schedule/report/activity data to a UI.
- **frontend** — a React + TypeScript dashboard for submitting reports, reviewing matches, and tracking project progress.

## Why this exists

Field reports arrive as messy text — typos, inconsistent equipment tags, informal phrasing — from DPRs and mobile field apps. Manually reconciling each one against a 100+ activity schedule is slow and error-prone. This system automates that reconciliation while being explicit about its own uncertainty: high-confidence matches update the schedule automatically, mid-confidence matches are queued for a human to confirm, and low-confidence ones are flagged as unmatched rather than guessed.

## Pipeline

```
RawReportInput
  → Module 1  Normalization        → NormalizedReport
  → Module 2  Extraction           → ExtractedReport
  → Module 3  Candidate Retrieval  → CandidateRetrievalResult
  → Module 4  Matching & Ranking   → RankingResult
  → Module 5  Decision             → DecisionResult
  → Module 6  Schedule Update      → UpdateResult

(System predictions + GroundTruthRecord) → Module 7  Evaluation → EvaluationResult
```

| Module | Responsibility |
|---|---|
| **1 — Normalization** | Rule-based cleanup of raw text: fixes known typos, expands abbreviations/aliases, standardizes equipment tags (e.g. `sp101` → `SP-101`), collapses whitespace. Preserves the original `raw_text` untouched. |
| **2 — Extraction** | Pulls structured signals out of the normalized text: equipment tags, locations, activity type, event type, and progress percentage. |
| **3 — Candidate Retrieval** | Narrows the full schedule (100+ activities) down to a top-K candidate set using a weighted hybrid of equipment/location/activity fuzzy matching and semantic similarity. Degrades gracefully to semantic-only when metadata is sparse. |
| **4 — Matching & Ranking** | Scores every candidate from Module 3 with an explainable, weighted formula (equipment, location, activity, date-plausibility, semantic signals) and returns them ranked. |
| **5 — Decision** | Turns the ranked candidates into one of three outcomes: `AUTO_MATCH` (≥ 0.85), `HUMAN_REVIEW` (0.60–0.85), or `UNMATCHED` (< 0.60). |
| **6 — Schedule Update** | Applies `AUTO_MATCH` decisions to a separate execution-state store (actual progress/status/timestamps) — the baseline Schedule Master is never modified. |
| **7 — Evaluation** | Compares system decisions against `ground_truth_v1.csv` offline: exact-match accuracy, per-decision accuracy/precision/recall, confusion matrix, and misclassification breakdowns. Ground truth never touches Modules 1–6. |

All shared data contracts (Pydantic models, enums, exceptions) live in **`shared/`** — every module imports from there rather than redefining its own shapes. See `shared/README.md` for the full contract and rules (e.g. `report_id` is preserved verbatim end-to-end, unknown values are `null`/`[]` not `"N/A"`, all scores are `0.0–1.0`).

## Repository layout

```
SIH2026-122-main/
├── Data/                    # Schedule master, raw reports, ground truth, execution state (CSV/JSON)
├── Engine/                  # The 7 pipeline modules (see table above)
│   ├── module_1_normalization/
│   ├── module_2_extraction/
│   ├── module_3_candidate/
│   ├── module_4_matching/
│   ├── module_5_decision/
│   ├── module_6_schedule_update/
│   └── module_7_evaluation/
├── shared/                  # Frozen cross-module contract: schemas, constants, exceptions, examples
├── integration/             # Pipeline orchestrator (chains Modules 1–7) + CLI + tests
├── backend/                 # FastAPI service (frontend ↔ backend ↔ pipeline)
├── frontend/                # React + TypeScript + Vite dashboard
├── scripts/                 # generate_domain_context.py — rebuilds shared vocabulary from the schedule
├── run_benchmark.py         # Fixed-denominator pipeline benchmark (accuracy + False Auto-Match Rate)
├── threshold_sweep.py       # Sweeps Module 5 thresholds against ground truth
├── tune_thresholds.py       # Tunes AUTO_MATCH / HUMAN_REVIEW thresholds
├── tune_weights.py          # Tunes Module 4 matching weights
├── analyze_189.py           # Root-cause analysis: attributes failures to the responsible module
├── breakdown.py             # Per-report decision/outcome breakdown against ground truth
├── pytest.ini
└── requirements.txt
```

## Getting started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the frontend)

### 1. Backend / Engine

```bash
pip install -r requirements.txt
pip install fastapi uvicorn --break-system-packages   # backend-only deps

# Run the pipeline end-to-end on a demo report
python -m integration --demo

# Run the pipeline on a specific report
python -m integration --report-id RPT-0001

# Start the API (from the repo root, next to Engine/, shared/, Data/)
uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload
```

The backend reads the schedule straight from `Data/schedule_master_v1.csv` and actual execution state from `Data/execution_state.csv` (written by Module 6) — there's no second database. It owns only the report/activity-update history that the pipeline itself doesn't track.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies API calls to port `5000`, matching the backend above — no additional configuration needed.

### 3. Tests

```bash
pytest
```

`pytest.ini` runs discovery over `Engine/` with the repo root on `pythonpath`.

## Evaluation & tuning workflow

- `python run_benchmark.py` — the canonical accuracy check. Reports a fixed-denominator breakdown (every report bucketed exactly once) plus **False Auto-Match Rate (FAMR)** — the rate of confidently-wrong automatic updates, which matters more than raw accuracy for a system that writes to the schedule.
- `python threshold_sweep.py` / `python tune_thresholds.py` — search Module 5's `AUTO_MATCH` / `HUMAN_REVIEW` thresholds against ground truth, subject to a maximum acceptable FAMR.
- `python tune_weights.py` — search Module 4's scoring weights.
- `python analyze_189.py` — separates failures by root cause (e.g. a low Module 3 candidate-recall ceiling vs. a Module 4/5 scoring/threshold problem), so tuning effort goes to the module that's actually responsible.
- `python breakdown.py` — per-report decision outcome vs. ground truth.

## Key design principles

1. **Contract-first.** Every module's input/output is a shared Pydantic schema; nobody invents local shapes.
2. **Ground truth isolation.** `GroundTruthRecord` is used only inside Module 7 — it never influences normalization, extraction, retrieval, matching, or decisions.
3. **Baseline vs. actual are separate.** Planned schedule fields (`planned_start`, `planned_finish`, `planned_duration_days`) are never written by any module; actual execution lives only in `ExecutionState`.
4. **Explainable scoring, not a black box.** Every match score is a weighted combination of named signals (equipment, location, activity, date, semantic), so a `HUMAN_REVIEW` or `UNMATCHED` outcome can be explained to a reviewer.
5. **Fail safe, not fail silent.** Uncertain matches are routed to human review rather than auto-applied; thresholds are tuned against a FAMR ceiling, not raw accuracy alone.

## Documentation

Each module and the `shared/` contract has its own `README.md` with full details on inputs, outputs, and rules:

- [`shared/README.md`](shared/README.md)
- [`Engine/module_1_normalization/README.md`](Engine/module_1_normalization/README.md)
- [`Engine/module_2_extraction/README.md`](Engine/module_2_extraction/README.md)
- [`Engine/module_5_decision/README.md`](Engine/module_5_decision/README.md)
- [`Engine/module_6_schedule_update/README.md`](Engine/module_6_schedule_update/README.md)
- [`Engine/module_7_evaluation/README.md`](Engine/module_7_evaluation/README.md)
