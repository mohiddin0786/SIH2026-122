"""
backend/batch_parser.py — Turns a bulk upload (Excel / PDF / pasted text /
UI multi-entry) into a list of raw report dicts, ready to be wrapped as
shared.schemas.RawReportInput and pushed through the existing pipeline
one at a time.

This module does NOT normalize, extract, or match anything — that's
Module 1-6's job, unchanged. It only answers one question: "how many
reports are in this upload, and what is each one's raw text?"

Output shape (list of dicts), one per detected report:
    {
        "text": str,            # raw_text, untouched
        "source_type": str,     # e.g. "spreadsheet", "pdf", "free_text", "frontend"
        "report_date": str | None,   # ISO date if we can detect one, else None
    }
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

SUPPORTED_EXCEL_EXT = (".xlsx", ".xls", ".csv")
SUPPORTED_PDF_EXT = (".pdf",)


def parse_upload(filename: str, file_bytes: bytes) -> list[dict]:
    """Dispatch by extension. Raises ValueError on unsupported/empty input."""
    lower = filename.lower()
    if lower.endswith(SUPPORTED_EXCEL_EXT):
        return parse_excel(file_bytes, filename)
    if lower.endswith(SUPPORTED_PDF_EXT):
        return parse_pdf(file_bytes)
    raise ValueError(f"Unsupported file type: {filename}")


# ---------------------------------------------------------------------------
# Excel / CSV
# ---------------------------------------------------------------------------

# Column names we'll guess as "the report text" column, in priority order.
_TEXT_COLUMN_CANDIDATES = (
    "report", "report_text", "text", "description", "notes",
    "raw_text", "update", "field_update", "remarks",
)
_DATE_COLUMN_CANDIDATES = ("date", "report_date", "reported_on", "timestamp")


def parse_excel(file_bytes: bytes, filename: str) -> list[dict]:
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)

    if df.empty:
        raise ValueError("Excel/CSV file has no rows")

    text_col = _find_column(df, _TEXT_COLUMN_CANDIDATES)
    if text_col is None:
        # Fallback: no recognizable header — assume the widest text-like
        # column is the report text (most chars on average).
        text_col = _guess_widest_text_column(df)

    date_col = _find_column(df, _DATE_COLUMN_CANDIDATES)

    reports = []
    for _, row in df.iterrows():
        text = str(row.get(text_col, "") or "").strip()
        if not text:
            continue  # skip blank rows silently
        report_date = _normalize_date(str(row.get(date_col, "") or "")) if date_col else None
        reports.append({
            "text": text,
            "source_type": "spreadsheet",
            "report_date": report_date,
        })

    if not reports:
        raise ValueError("No non-empty report rows found — check the text column")
    return reports


def _find_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> Optional[str]:
    lower_map = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    return None


def _guess_widest_text_column(df: pd.DataFrame) -> str:
    avg_lengths = {
        col: df[col].astype(str).str.len().mean()
        for col in df.columns
    }
    return max(avg_lengths, key=avg_lengths.get)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def parse_pdf(file_bytes: bytes) -> list[dict]:
    """
    Extract text from PDF, then split into individual reports.

    Splitting heuristic (in priority order):
      1. If the doc has multiple pages and most pages look like one report
         each (short, self-contained), split by page.
      2. Otherwise split on blank-line gaps or a leading date pattern
         (e.g. "2026-08-28" or "28/08/2026" at the start of a line), since
         daily-diary-style PDFs usually stack entries this way.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError(
            "pdfplumber not installed — add it to requirements.txt"
        ) from e

    pages_text = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            pages_text.append((page.extract_text() or "").strip())

    if not any(pages_text):
        raise ValueError("No extractable text found in PDF (may be scanned/image-only)")

    # Heuristic 1: multi-page, each page non-trivial and reasonably short
    # -> treat each page as one report.
    non_empty_pages = [p for p in pages_text if p]
    if len(non_empty_pages) > 1 and all(len(p) < 3000 for p in non_empty_pages):
        return [
            {"text": p, "source_type": "pdf", "report_date": _extract_leading_date(p)}
            for p in non_empty_pages
        ]

    # Heuristic 2: single blob (one page or one huge page) -> split on
    # date-marker lines or blank-line gaps.
    full_text = "\n\n".join(non_empty_pages)
    return _split_text_blob(full_text, source_type="pdf")


# ---------------------------------------------------------------------------
# Pasted raw text / notes
# ---------------------------------------------------------------------------

def parse_raw_text(blob: str) -> list[dict]:
    if not blob or not blob.strip():
        raise ValueError("Pasted text is empty")
    return _split_text_blob(blob, source_type="free_text")


_DATE_LINE_RE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
)


def _split_text_blob(blob: str, source_type: str) -> list[dict]:
    # Prefer splitting on lines that start with a date — common in daily
    # diaries / stacked notes ("2026-08-28: SP101 installed...").
    lines = blob.splitlines()
    date_line_idxs = [i for i, ln in enumerate(lines) if _DATE_LINE_RE.match(ln)]

    if len(date_line_idxs) >= 2:
        chunks = []
        for start, end in zip(date_line_idxs, date_line_idxs[1:] + [len(lines)]):
            chunk = "\n".join(lines[start:end]).strip()
            if chunk:
                chunks.append(chunk)
    else:
        # Fallback: split on blank-line gaps (paragraph breaks).
        chunks = [c.strip() for c in re.split(r"\n\s*\n+", blob) if c.strip()]

    if not chunks:
        chunks = [blob.strip()]

    return [
        {
            "text": c,
            "source_type": source_type,
            "report_date": _extract_leading_date(c),
        }
        for c in chunks
    ]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_leading_date(text: str) -> Optional[str]:
    m = _DATE_LINE_RE.match(text.strip())
    if not m:
        return None
    return _normalize_date(m.group(1))


def _normalize_date(raw: str) -> Optional[str]:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None