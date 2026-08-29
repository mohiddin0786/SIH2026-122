import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from shared.schemas import (
    NormalizedReport,
    ExtractedReport,
    ExtractedEntity,
    ExtractedNumericValue,
    ActivityTypeValue,
    EventTypeValue,
)

from shared.constants import ActivityType, EventType


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"


def load_json_config(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


ACTIVITY_ALIASES = load_json_config("activity_aliases.json")
LOCATIONS_CONFIG = load_json_config("locations.json")

EQUIPMENT_TAG_PATTERN = re.compile(
    r"\b[A-Z]{1,4}-\d{2,5}[A-Z]?\b",
    re.IGNORECASE,
)


def extract_equipment_tags(text: str) -> List[ExtractedEntity]:
    matches = EQUIPMENT_TAG_PATTERN.findall(text)

    seen = set()
    results = []

    for match in matches:
        normalized_match = match.upper()

        if normalized_match in seen:
            continue

        seen.add(normalized_match)

        results.append(
            ExtractedEntity(
                value=normalized_match,
                confidence=0.95,
            )
        )

    return results

def extract_locations(text: str) -> List[ExtractedEntity]:
    configured_locations = LOCATIONS_CONFIG.get("locations", [])

    # Check longer/more specific locations first.
    sorted_locations = sorted(
        configured_locations,
        key=len,
        reverse=True,
    )

    matched_locations = []

    for location in sorted_locations:
        pattern = re.compile(
            rf"\b{re.escape(location)}\b",
            re.IGNORECASE,
        )

        if pattern.search(text):
            # Do not add a shorter location if it is already
            # contained inside a more specific matched location.
            if any(
                location.lower() in existing.lower()
                for existing in matched_locations
            ):
                continue

            matched_locations.append(location)

    return [
        ExtractedEntity(
            value=location,
            confidence=0.90,
        )
        for location in matched_locations
    ]

def extract_activity_type(text: str) -> ActivityTypeValue:
    text_lower = text.lower()
    matches = []

    for activity_name, aliases in ACTIVITY_ALIASES.items():
        for alias in aliases:
            pattern = re.compile(
                rf"\b{re.escape(alias.lower())}\b",
                re.IGNORECASE,
            )

            if pattern.search(text_lower):
                matches.append(activity_name)
                break

    unique_matches = list(dict.fromkeys(matches))

    if not unique_matches:
        return ActivityTypeValue(
            value=ActivityType.UNKNOWN,
            confidence=0.0,
        )

    if len(unique_matches) > 1:
        return ActivityTypeValue(
            value=ActivityType.UNKNOWN,
            confidence=0.3,
        )

    activity_enum = ActivityType(unique_matches[0])

    return ActivityTypeValue(
        value=activity_enum,
        confidence=0.92,
    )

def extract_event_type(text: str) -> EventTypeValue:
    text_lower = text.lower()

    # Percentage mentioned means the work is in progress.
    # Example: "10% complete", "60% completed"
    if re.search(
        r"\b\d+(?:\.\d+)?\s*%\s*(?:complete|completed)?\b",
        text_lower,
    ):
        return EventTypeValue(
            value=EventType.PROGRESS,
            confidence=0.88,
        )

    # Work is fully finished.
    finish_patterns = [
        r"\bcompleted\b",
        r"\bcomplete\b",
        r"\bfinished\b",
        r"\bdone\b",
    ]

    for pattern in finish_patterns:
        if re.search(pattern, text_lower):
            return EventTypeValue(
                value=EventType.FINISH,
                confidence=0.95,
            )

    # Work is currently happening.
    progress_patterns = [
        r"\bin progress\b",
        r"\bongoing\b",
        r"\bprogressing\b",
    ]

    for pattern in progress_patterns:
        if re.search(pattern, text_lower):
            return EventTypeValue(
                value=EventType.PROGRESS,
                confidence=0.88,
            )

    # Work has just started.
    start_patterns = [
        r"\bstarted\b",
        r"\bstart\b",
        r"\bcommenced\b",
        r"\bbegan\b",
    ]

    for pattern in start_patterns:
        if re.search(pattern, text_lower):
            return EventTypeValue(
                value=EventType.START,
                confidence=0.90,
            )

    # Nothing reliable was found.
    return EventTypeValue(
        value=EventType.UNKNOWN,
        confidence=0.0,
    )


def extract_progress(
    text: str,
    event_type: EventTypeValue,
) -> ExtractedNumericValue:

    # First look for an explicit percentage.
    percentage_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*%",
        text,
        re.IGNORECASE,
    )

    if percentage_match:
        value = float(percentage_match.group(1))

        if 0.0 <= value <= 100.0:
            return ExtractedNumericValue(
                value=value,
                confidence=0.90,
            )

    # Completed work means 100%.
    if event_type.value == EventType.FINISH:
        return ExtractedNumericValue(
            value=100.0,
            confidence=0.95,
        )

    # Started work means 0%.
    if event_type.value == EventType.START:
        return ExtractedNumericValue(
            value=0.0,
            confidence=0.90,
        )

    # Never guess progress.
    return ExtractedNumericValue(
        value=None,
        confidence=0.0,
    )

def extract_information(report: NormalizedReport) -> ExtractedReport:
    equipment_tags = extract_equipment_tags(report.normalized_text)
    locations = extract_locations(report.normalized_text)
    activity_type = extract_activity_type(report.normalized_text)
    event_type = extract_event_type(report.normalized_text)
    progress = extract_progress(report.normalized_text, event_type)

    extraction_flags = []

    if not equipment_tags:
        extraction_flags.append("NO_EQUIPMENT_TAG")

    if not locations:
        extraction_flags.append("NO_LOCATION")

    if activity_type.value == ActivityType.UNKNOWN:
        extraction_flags.append("UNKNOWN_ACTIVITY_TYPE")

    if event_type.value == EventType.UNKNOWN:
        extraction_flags.append("UNKNOWN_EVENT_TYPE")

    if progress.value is None:
        extraction_flags.append("PROGRESS_UNDETERMINED")

    return ExtractedReport(
        report_id=report.report_id,
        normalized_text=report.normalized_text,
        equipment_tags=equipment_tags,
        locations=locations,
        activity_type=activity_type,
        event_type=event_type,
        progress=progress,
        extraction_flags=extraction_flags,
    )

