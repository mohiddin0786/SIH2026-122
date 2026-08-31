"""
python_backend/main.py — The whole backend. Frontend <-> this <-> Pipeline.

Replaces the Node/Express/Mongoose layer entirely. No second database: the
schedule (planned dates, names, locations) comes straight from
Data/schedule_master_v1.csv, and current activity status/progress comes
straight from Module 6's own Data/execution_state.csv (via
ExecutionStateRepository, which the pipeline already writes to on
AUTO_MATCH). The only new state this file owns is FieldReport records and
ActivityUpdate history (see store.py) — things the pipeline itself has no
reason to remember.

Run from the repo root (next to Engine/, shared/, integration/, Data/):

    pip install fastapi uvicorn --break-system-packages
    uvicorn python_backend.main:app --host 0.0.0.0 --port 5000 --reload

Port 5000 matches the frontend's existing vite.config.ts proxy — no
frontend changes needed.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.constants import DecisionType, ExecutionStatus
from shared.schemas import RawReportInput, ExecutionState
from integration.pipeline import Pipeline
from Engine.module_6_schedule_update.repository import ExecutionStateRepository
from Engine.module_6_schedule_update.config import ScheduleUpdateConfig

from . import batch_parser
from .store import store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("python_backend")

PROJECT_ID = "proj-sih26122"
SCHEDULE_MASTER_PATH = "Data/schedule_master_v1.csv"

_state: Dict[str, object] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Building schedule index / pipeline ...")
    config = ScheduleUpdateConfig(schedule_master_path=SCHEDULE_MASTER_PATH)
    _state["pipeline"] = Pipeline(schedule_master_path=SCHEDULE_MASTER_PATH)
    _state["exec_repo"] = ExecutionStateRepository(config)
    _state["schedule_df"] = pd.read_csv(SCHEDULE_MASTER_PATH, dtype=str, keep_default_na=False)
    logger.info("Ready — %d activities loaded.", len(_state["schedule_df"]))
    yield
    _state.clear()


app = FastAPI(title="SIH2026-122 Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def envelope(data=None, error: Optional[str] = None, message: Optional[str] = None) -> dict:
    """Matches the frontend's ApiResponse<T> contract: {success, data, error, message}."""
    return {"success": error is None, "data": data, "error": error, "message": message}


def fail(status_code: int, error: str):
    raise HTTPException(status_code=status_code, detail=error)


# ---------------------------------------------------------------------------
# Activity view — merges schedule_master (planned) + execution_state (actual)
# ---------------------------------------------------------------------------


def _pipeline() -> Pipeline:
    return _state["pipeline"]  # type: ignore[return-value]


def _exec_repo() -> ExecutionStateRepository:
    return _state["exec_repo"]  # type: ignore[return-value]


def _schedule_df() -> pd.DataFrame:
    return _state["schedule_df"]  # type: ignore[return-value]


_STATUS_MAP = {
    "NOT_STARTED": "NOT_STARTED",
    "IN_PROGRESS": "IN_PROGRESS",
    "COMPLETED": "COMPLETED",
    "UNKNOWN": "NOT_STARTED",
}


def _activity_view(row: pd.Series) -> dict:
    activity_id = row["activity_id"]
    exec_state: Optional[ExecutionState] = _exec_repo().get(activity_id)

    if exec_state is not None:
        status = _STATUS_MAP.get(exec_state.actual_status.value, "NOT_STARTED")
        progress = exec_state.actual_progress if exec_state.actual_progress is not None else 0
        last_report_id = exec_state.last_report_id
        timestamp = exec_state.last_update_timestamp
    else:
        status, progress, last_report_id, timestamp = "NOT_STARTED", 0, None, None

    return {
        "_id": activity_id,
        "projectId": PROJECT_ID,
        "name": row["activity_name"],
        "description": row.get("activity_description") or row["activity_name"],
        "status": status,
        "progress": progress,
        "plannedStart": row["planned_start"],
        "plannedFinish": row["planned_finish"],
        "actualStart": timestamp if status == "IN_PROGRESS" else None,
        "actualFinish": timestamp if status == "COMPLETED" else None,
        "location": row.get("location") or "Unspecified",
        "priority": "MEDIUM",
        "assignedTo": row.get("discipline") or None,
        "latestReportId": last_report_id,
        "createdAt": timestamp or "2026-01-01T00:00:00Z",
        "updatedAt": timestamp or "2026-01-01T00:00:00Z",
    }


def _get_activity_row(activity_id: str) -> Optional[pd.Series]:
    df = _schedule_df()
    matches = df[df["activity_id"] == activity_id]
    return matches.iloc[0] if not matches.empty else None


def _get_activity_view(activity_id: str) -> Optional[dict]:
    row = _get_activity_row(activity_id)
    return _activity_view(row) if row is not None else None


def _build_update_message(prev_status, new_status, prev_progress, new_progress) -> str:
    def fmt(s):
        return {
            "NOT_STARTED": "Not Started",
            "IN_PROGRESS": "In Progress",
            "COMPLETED": "Completed",
        }.get(s, s or "Unknown")

    if new_status == "COMPLETED":
        return "Marked as completed"
    if prev_status != new_status and prev_progress != new_progress:
        return f"Status changed to {fmt(new_status)}, progress {prev_progress or 0}% \u2192 {new_progress or 0}%"
    if prev_status != new_status:
        return f"Status changed to {fmt(new_status)}"
    if prev_progress != new_progress:
        return f"Progress updated {prev_progress or 0}% \u2192 {new_progress or 0}%"
    return "Activity updated from field report"


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def _project_view() -> dict:
    return {
        "_id": PROJECT_ID,
        "name": "PS SIH26122 \u2014 Oil India Limited Smart Automation",
        "description": "Field report to schedule activity matching",
        "location": "Oil India Limited construction site",
        "startDate": "2026-01-01T00:00:00Z",
        "plannedEndDate": "2026-12-31T00:00:00Z",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


@app.get("/api/projects")
def list_projects():
    return envelope([_project_view()])


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    if project_id != PROJECT_ID:
        fail(404, f"Project {project_id} not found")
    return envelope(_project_view())


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@app.get("/api/projects/{project_id}/activities")
def list_activities(project_id: str):
    if project_id != PROJECT_ID:
        fail(404, f"Project {project_id} not found")
    df = _schedule_df()
    return envelope([_activity_view(row) for _, row in df.iterrows()])


@app.get("/api/activities/{activity_id}")
def get_activity(activity_id: str):
    view = _get_activity_view(activity_id)
    if view is None:
        fail(404, f"Activity {activity_id} not found")
    return envelope(view)


@app.get("/api/activities/{activity_id}/updates")
def get_activity_updates(activity_id: str):
    return envelope(store.list_updates_for_activity(activity_id))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class SubmitReportBody(BaseModel):
    text: str


class BatchItem(BaseModel):
    text: str
    sourceType: Optional[str] = None
    reportDate: Optional[str] = None


class SubmitBatchBody(BaseModel):
    items: List[BatchItem]


class ConfirmBody(BaseModel):
    activityId: str


class RejectBody(BaseModel):
    note: Optional[str] = None


@app.get("/api/projects/{project_id}/reports")
def list_reports(project_id: str):
    return envelope(store.list_reports(project_id))


@app.get("/api/projects/{project_id}/attention")
def list_attention(project_id: str):
    return envelope(store.list_attention_reports(project_id))


@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    record = store.get_report(report_id)
    if record is None:
        fail(404, f"Report {report_id} not found")
    return envelope(record)


def _process_single_report(project_id: str, text: str, source_type: str = "frontend",
                            report_date: Optional[str] = None) -> dict:
    if not text or not text.strip():
        return {"status": "ERROR", "error": "Report text must not be empty"}

    report_id = store.new_report_id()
    raw_report = RawReportInput(
        report_id=report_id,
        report_date=report_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        source_type=source_type,
        raw_text=text,
    )

    result = _pipeline().process_report(raw_report)

    if result.failed():
        failed = result.failed_stage()
        logger.warning("Pipeline failed for %s at %s: %s", report_id,
                        failed.stage if failed else "?", failed.error if failed else "?")
        store.create_report(report_id, project_id, text, status="UNMATCHED")
        return {"status": "UNMATCHED", "reportId": report_id}

    decision = result.decision
    assert decision is not None

    if decision.decision == DecisionType.AUTO_MATCH:
        activity_id = decision.selected_activity_id
        update = result.update
        prev_state = update.previous_execution_state if update else None
        new_state = update.new_execution_state if update else None
        prev_status = _STATUS_MAP.get(prev_state.actual_status.value, "NOT_STARTED") if prev_state else "NOT_STARTED"
        new_status = _STATUS_MAP.get(new_state.actual_status.value, "NOT_STARTED") if new_state else "NOT_STARTED"
        prev_progress = prev_state.actual_progress if prev_state else 0
        new_progress = new_state.actual_progress if new_state else 0

        message = _build_update_message(prev_status, new_status, prev_progress, new_progress)
        update_record = store.add_update(
            activity_id, report_id, prev_status, new_status, prev_progress, new_progress, message
        )
        store.create_report(report_id, project_id, text, status="SUCCESS", matched_activity_id=activity_id)
        return {
            "status": "SUCCESS",
            "reportId": report_id,
            "activity": _get_activity_view(activity_id),
            "update": update_record,
        }

    if decision.decision == DecisionType.HUMAN_REVIEW:
        candidates = [
            {"activityId": c.activity_id, "activityName": c.activity_name}
            for c in (result.ranking.ranked_candidates[:3] if result.ranking else [])
        ]
        store.create_report(report_id, project_id, text, status="NEEDS_REVIEW", candidate_activities=candidates)
        return {"status": "NEEDS_REVIEW", "reportId": report_id, "candidates": candidates}

    store.create_report(report_id, project_id, text, status="UNMATCHED")
    return {"status": "UNMATCHED", "reportId": report_id}


@app.post("/api/projects/{project_id}/reports")
def submit_report(project_id: str, body: SubmitReportBody):
    if project_id != PROJECT_ID:
        fail(404, f"Project {project_id} not found")
    result = _process_single_report(project_id, body.text, source_type="frontend")
    if result.get("status") == "ERROR":
        fail(400, result["error"])
    return envelope(result)


@app.post("/api/projects/{project_id}/reports/batch")
def submit_batch(project_id: str, body: SubmitBatchBody):
    if project_id != PROJECT_ID:
        fail(404, f"Project {project_id} not found")
    if not body.items:
        fail(400, "No items provided")

    results = []
    for item in body.items:
        try:
            r = _process_single_report(
                project_id, item.text,
                source_type=item.sourceType or "batch",
                report_date=item.reportDate,
            )
        except Exception as e:
            logger.exception("Batch item failed")
            r = {"status": "ERROR", "error": str(e)}
        results.append(r)

    summary = {
        "total": len(results),
        "success": sum(1 for r in results if r.get("status") == "SUCCESS"),
        "needsReview": sum(1 for r in results if r.get("status") == "NEEDS_REVIEW"),
        "unmatched": sum(1 for r in results if r.get("status") == "UNMATCHED"),
        "errors": sum(1 for r in results if r.get("status") == "ERROR"),
    }
    return envelope({"results": results, "summary": summary})


@app.post("/api/projects/{project_id}/reports/parse")
async def parse_batch_upload(
    project_id: str,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
):
    if project_id != PROJECT_ID:
        fail(404, f"Project {project_id} not found")
    try:
        if file is not None:
            contents = await file.read()
            parsed = batch_parser.parse_upload(file.filename, contents)
        elif text is not None:
            parsed = batch_parser.parse_raw_text(text)
        else:
            fail(400, "Provide either a file or text")
    except ValueError as e:
        fail(400, str(e))
    except RuntimeError as e:
        fail(500, str(e))
    return envelope({"items": parsed, "count": len(parsed)})


@app.post("/api/reports/{report_id}/confirm")
def confirm_activity(report_id: str, body: ConfirmBody):
    report = store.get_report(report_id)
    if report is None:
        fail(404, f"Report {report_id} not found")

    activity_row = _get_activity_row(body.activityId)
    if activity_row is None:
        fail(404, f"Activity {body.activityId} not found")

    exec_repo = _exec_repo()
    prev_state = exec_repo.get(body.activityId)
    prev_status = _STATUS_MAP.get(prev_state.actual_status.value, "NOT_STARTED") if prev_state else "NOT_STARTED"
    prev_progress = prev_state.actual_progress if prev_state else 0

    new_progress = max(prev_progress or 0, 50)
    new_state = ExecutionState(
        activity_id=body.activityId,
        actual_status=ExecutionStatus.IN_PROGRESS,
        actual_progress=new_progress,
        last_report_id=report_id,
        last_update_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    exec_repo.save(new_state)

    update_record = store.add_update(
        body.activityId, report_id, prev_status, "IN_PROGRESS", prev_progress, new_progress,
        f"Activity confirmed via Field Report {report_id}",
    )

    store.update_report(report_id, status="SUCCESS", matchedActivityId=body.activityId, userDecision="CONFIRMED")

    return envelope({
        "status": "SUCCESS",
        "reportId": report_id,
        "activity": _get_activity_view(body.activityId),
        "update": update_record,
    })


@app.post("/api/reports/{report_id}/reject")
def reject_report(report_id: str, body: RejectBody):
    report = store.update_report(report_id, status="UNMATCHED", userDecision="REJECTED", reviewNote=body.note)
    if report is None:
        fail(404, f"Report {report_id} not found")
    return envelope({"status": "UNMATCHED", "reportId": report_id})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@app.get("/api/projects/{project_id}/dashboard")
def dashboard(project_id: str):
    if project_id != PROJECT_ID:
        fail(404, f"Project {project_id} not found")

    df = _schedule_df()
    activities = [_activity_view(row) for _, row in df.iterrows()]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = len(activities)
    completed_today = sum(
        1 for a in activities if a["status"] == "COMPLETED" and (a["updatedAt"] or "").startswith(today)
    )
    in_progress = sum(1 for a in activities if a["status"] == "IN_PROGRESS")
    needs_attention = len(store.list_attention_reports(project_id))
    avg_progress = round(sum(a["progress"] for a in activities) / total) if total else 0

    recent = []
    for u in store.list_recent_updates(limit=10):
        activity = _get_activity_view(u["activityId"])
        if activity is None:
            continue
        recent.append({
            **u,
            "activity": {"_id": activity["_id"], "name": activity["name"], "status": activity["status"]},
        })

    return envelope({
        "project": _project_view(),
        "totalActivities": total,
        "completedToday": completed_today,
        "inProgress": in_progress,
        "needsAttention": needs_attention,
        "progress": avg_progress,
        "recentUpdates": recent,
    })


@app.get("/health")
def health():
    return {"status": "ok", "activities_loaded": len(_schedule_df()) if "schedule_df" in _state else 0}
