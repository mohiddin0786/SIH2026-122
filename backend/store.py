"""
python_backend/store.py — Lightweight persistence for the two things the
Python pipeline itself does NOT track:

  1. FieldReport records (submitted text, decision status, candidates,
     human review/reject actions) — the pipeline processes a report and
     hands back a DecisionResult, it doesn't remember the report happened.
  2. ActivityUpdate history (a timeline of "what changed and when") — Module
     6's ExecutionStateRepository only keeps the CURRENT state per activity,
     not a history log.

Everything else (planned schedule, current activity status/progress) is
read straight from Data/schedule_master_v1.csv and Module 6's own
Data/execution_state.csv — no duplication, no second source of truth.

Uses a single JSON file for simple, transparent, restart-safe persistence,
consistent with the CSV-based approach Module 6 already uses. Fine for a
single-writer hackathon demo; not a concurrency-safe production store.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

STORE_PATH = Path("Data/api_state.json")

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ApiStateStore:
    """In-memory store, mirrored to a JSON file on every write."""

    def __init__(self, path: Path = STORE_PATH):
        self.path = path
        self.reports: Dict[str, dict] = {}
        self.updates: List[dict] = []
        self._report_counter = 0
        self._update_counter = 0
        self._load()

    # -- persistence -------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self.reports = data.get("reports", {})
        self.updates = data.get("updates", [])
        self._report_counter = data.get("report_counter", len(self.reports))
        self._update_counter = data.get("update_counter", len(self.updates))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "reports": self.reports,
            "updates": self.updates,
            "report_counter": self._report_counter,
            "update_counter": self._update_counter,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # -- reports -------------------------------------------------------

    def new_report_id(self) -> str:
        with _lock:
            self._report_counter += 1
            return f"RPT-{self._report_counter:05d}"

    def create_report(
        self,
        report_id: str,
        project_id: str,
        text: str,
        status: str,
        matched_activity_id: Optional[str] = None,
        candidate_activities: Optional[List[dict]] = None,
    ) -> dict:
        now = _now_iso()
        record = {
            "_id": report_id,
            "reportId": report_id,
            "projectId": project_id,
            "text": text,
            "submittedAt": now,
            "status": status,
            "matchedActivityId": matched_activity_id,
            "candidateActivities": candidate_activities or [],
            "userDecision": None,
            "reviewNote": None,
            "createdAt": now,
            "updatedAt": now,
        }
        with _lock:
            self.reports[report_id] = record
            self._save()
        return record

    def update_report(self, report_id: str, **fields) -> Optional[dict]:
        with _lock:
            record = self.reports.get(report_id)
            if record is None:
                return None
            record.update(fields)
            record["updatedAt"] = _now_iso()
            self._save()
            return record

    def get_report(self, report_id: str) -> Optional[dict]:
        return self.reports.get(report_id)

    def list_reports(self, project_id: str) -> List[dict]:
        return sorted(
            (r for r in self.reports.values() if r["projectId"] == project_id),
            key=lambda r: r["submittedAt"],
            reverse=True,
        )

    def list_attention_reports(self, project_id: str) -> List[dict]:
        return [
            r
            for r in self.list_reports(project_id)
            if r["status"] in ("NEEDS_REVIEW", "UNMATCHED") and r.get("userDecision") is None
        ]

    # -- activity update history -------------------------------------------------------

    def add_update(
        self,
        activity_id: str,
        report_id: str,
        previous_status: Optional[str],
        new_status: Optional[str],
        previous_progress: Optional[float],
        new_progress: Optional[float],
        message: str,
    ) -> dict:
        with _lock:
            self._update_counter += 1
            record = {
                "_id": f"UPD-{self._update_counter:05d}",
                "activityId": activity_id,
                "reportId": report_id,
                "previousStatus": previous_status,
                "newStatus": new_status,
                "previousProgress": previous_progress,
                "newProgress": new_progress,
                "message": message,
                "createdAt": _now_iso(),
            }
            self.updates.append(record)
            self._save()
            return record

    def list_updates_for_activity(self, activity_id: str) -> List[dict]:
        return sorted(
            (u for u in self.updates if u["activityId"] == activity_id),
            key=lambda u: u["createdAt"],
            reverse=True,
        )

    def list_recent_updates(self, limit: int = 10) -> List[dict]:
        return sorted(self.updates, key=lambda u: u["createdAt"], reverse=True)[:limit]


store = ApiStateStore()
