import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from shared.schemas import (
    NormalizedReport,
    ExtractedReport,
    ExtractedEntity,
    ExtractedNumericValue,
    ActivityTypeValue,
    EventTypeValue,
)

from shared.constants import ActivityType, EventType

logger = logging.getLogger(__name__)

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

_WORD_TO_NUM: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100,
}

GENERIC_LOCATION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Unit", re.compile(r"\bUnit\s+(\d+)\b", re.IGNORECASE)),
    ("Area", re.compile(r"\bArea\s+([A-Za-z0-9])\b", re.IGNORECASE)),
    ("Zone", re.compile(r"\bZone\s+([A-Za-z0-9])\b", re.IGNORECASE)),
    ("Block", re.compile(r"\bBlock\s+([A-Za-z0-9])\b", re.IGNORECASE)),
]

# ---------------------------------------------------------------------------
# activity_type fallback layers
#
# Layer 1 (below, existing): exact word-boundary alias match. Fast, highest
# precision, but silently returns UNKNOWN on any phrasing not in
# activity_aliases.json -- measured at ~40% of raw_reports_v1.csv before
# these fallbacks were added, since that file used to be a static hand-typed
# list. It's now regenerated from schedule_master_v1.csv by
# scripts/generate_domain_context.py, which closes most of that gap, but
# typos and genuinely novel phrasing still need something more forgiving:
#
# Layer 2: fuzzy match (rapidfuzz) against the same alias words -- catches
# typos/inflections the mined list doesn't have verbatim (e.g. "inspec").
#
# Layer 3: semantic similarity (reuses module_3_candidate's SemanticBackend,
# the same embedder already used for schedule-candidate retrieval) against
# one canonical sentence per ActivityType, built from that type's alias
# words. Catches phrasing that's conceptually right but shares no words
# with the alias list at all.
#
# Each layer is strictly a fallback -- only tried if the previous layer
# found nothing -- and each is progressively lower-confidence. Which layer
# resolved the value is recorded in ExtractedReport.extraction_flags (see
# extract_information) so it's visible for audit / "why" explanations.
#
# IMPORTANT (see decision.py gating): a value resolved via fuzzy/semantic
# fallback is a GUESS, not a confident match -- Module 5 must not let a
# report with these flags reach AUTO_MATCH on the strength of that guess.
# ---------------------------------------------------------------------------

ACTIVITY_FUZZY_FLOOR = 85     # rapidfuzz partial_ratio, 0-100
ACTIVITY_SEMANTIC_FLOOR = 0.35  # cosine similarity, backend-dependent scale

_semantic_backend = None
_activity_type_keys: List[str] = []
_activity_canonical_embeddings = None


def _get_activity_semantic_index():
    """Lazily builds (and caches) a semantic embedding for one canonical
    sentence per ActivityType, derived from ACTIVITY_ALIASES. Import of
    SemanticBackend is deferred and guarded so Module 2 doesn't hard-fail
    if module_3 or its embedding deps aren't available in a given
    environment -- semantic fallback simply won't fire, and layer 1/2
    still work."""
    global _semantic_backend, _activity_type_keys, _activity_canonical_embeddings

    if _activity_canonical_embeddings is not None:
        return _semantic_backend, _activity_type_keys, _activity_canonical_embeddings

    try:
        from Engine.module_3_candidate.semantic_backend import SemanticBackend
    except Exception as exc:  # noqa: BLE001 - graceful degrade, same pattern as semantic_backend.py itself
        logger.warning(
            "extract_activity_type: could not import SemanticBackend (%s). "
            "Semantic fallback layer disabled; exact + fuzzy layers still active.",
            exc,
        )
        _semantic_backend = False  # sentinel: "tried and unavailable"
        _activity_type_keys = []
        _activity_canonical_embeddings = []
        return _semantic_backend, _activity_type_keys, _activity_canonical_embeddings

    keys = list(ACTIVITY_ALIASES.keys())
    canonical_texts = [" ".join(ACTIVITY_ALIASES[k]) for k in keys]

    backend = SemanticBackend()
    backend.fit_corpus(canonical_texts)  # no-op in sbert mode, required in tfidf mode
    embeddings = backend.embed(canonical_texts)

    _semantic_backend = backend
    _activity_type_keys = keys
    _activity_canonical_embeddings = embeddings
    return _semantic_backend, _activity_type_keys, _activity_canonical_embeddings


def _word_to_num(word: str) -> Optional[int]:
    w = word.lower().strip()
    if w in _WORD_TO_NUM:
        return _WORD_TO_NUM[w]
    return None


def _extract_generic_locations(text: str) -> List[str]:
    matches: List[str] = []
    seen: set = set()

    for keyword, pattern in GENERIC_LOCATION_PATTERNS:
        for match in pattern.finditer(text):
            label = match.group(1)
            location = f"{keyword} {label}"
            loc_key = location.lower()
            if loc_key not in seen:
                seen.add(loc_key)
                matches.append(location)

    return matches


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

    # Add generic locations (Unit, Area, Zone, Block) that are not
    # already part of a more specific exact match.
    for generic_location in _extract_generic_locations(text):
        if any(
            generic_location.lower() in existing.lower()
            for existing in matched_locations
        ):
            continue
        matched_locations.append(generic_location)

    return [
        ExtractedEntity(
            value=location,
            confidence=0.90,
        )
        for location in matched_locations
    ]


def _extract_activity_type_exact(text_lower: str) -> List[str]:
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
    return list(dict.fromkeys(matches))


def _extract_activity_type_fuzzy(text_lower: str) -> Optional[Tuple[str, float]]:
    """Layer 2. Compares the whole report text against every alias word
    with rapidfuzz.partial_ratio (substring-tolerant, typo-tolerant).
    Returns (activity_type, ratio 0-100) for the single best match above
    ACTIVITY_FUZZY_FLOOR, or None."""
    try:
        from rapidfuzz import fuzz
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "extract_activity_type: rapidfuzz unavailable (%s). "
            "Fuzzy fallback layer disabled.", exc,
        )
        return None

    best_type: Optional[str] = None
    best_score = 0.0

    for activity_name, aliases in ACTIVITY_ALIASES.items():
        for alias in aliases:
            score = fuzz.partial_ratio(alias.lower(), text_lower)
            if score > best_score:
                best_score = score
                best_type = activity_name

    if best_type is not None and best_score >= ACTIVITY_FUZZY_FLOOR:
        return best_type, best_score
    return None


def _extract_activity_type_semantic(text: str) -> Optional[Tuple[str, float]]:
    """Layer 3. Embeds the report text and compares against one canonical
    sentence per ActivityType (built from ACTIVITY_ALIASES). Returns
    (activity_type, cosine similarity) for the best match above
    ACTIVITY_SEMANTIC_FLOOR, or None."""
    backend, keys, embeddings = _get_activity_semantic_index()
    if not backend or len(keys) == 0:
        return None

    import numpy as np  # local import: only needed on this fallback path

    query_vec = backend.embed([text])[0]
    sims = backend.cosine_sim(query_vec, np.asarray(embeddings))
    if len(sims) == 0:
        return None

    best_idx = int(np.argmax(sims))
    best_score = float(sims[best_idx])
    if best_score >= ACTIVITY_SEMANTIC_FLOOR:
        return keys[best_idx], best_score
    return None


def extract_activity_type(text: str) -> Tuple[ActivityTypeValue, Optional[str]]:
    """Returns (ActivityTypeValue, source_flag). source_flag is None when
    resolved by the exact-match layer (the common case), otherwise one of
    "ACTIVITY_TYPE_VIA_FUZZY" / "ACTIVITY_TYPE_VIA_SEMANTIC" so callers can
    surface which layer produced the answer -- and so Module 5 can refuse
    to AUTO_MATCH on an unverified guess (see decision.py)."""
    text_lower = text.lower()

    unique_matches = _extract_activity_type_exact(text_lower)

    if len(unique_matches) == 1:
        return (
            ActivityTypeValue(
                value=ActivityType(unique_matches[0]),
                confidence=0.92,
            ),
            None,
        )

    if len(unique_matches) > 1:
        # Ambiguous exact match (2+ different activity types both matched).
        # Checked against the real dataset -- this branch doesn't currently
        # fire on raw_reports_v1.csv -- but we still don't want to silently
        # guess here, so it stays UNKNOWN rather than falling through to
        # fuzzy/semantic, which would be even less reliable on text that's
        # already known to be ambiguous.
        return (
            ActivityTypeValue(
                value=ActivityType.UNKNOWN,
                confidence=0.3,
            ),
            None,
        )

    # No exact match at all -- try fuzzy, then semantic.
    fuzzy_result = _extract_activity_type_fuzzy(text_lower)
    if fuzzy_result is not None:
        activity_name, score = fuzzy_result
        return (
            ActivityTypeValue(
                value=ActivityType(activity_name),
                confidence=0.65,
            ),
            "ACTIVITY_TYPE_VIA_FUZZY",
        )

    semantic_result = _extract_activity_type_semantic(text)
    if semantic_result is not None:
        activity_name, score = semantic_result
        return (
            ActivityTypeValue(
                value=ActivityType(activity_name),
                confidence=0.5,
            ),
            "ACTIVITY_TYPE_VIA_SEMANTIC",
        )

    return (
        ActivityTypeValue(
            value=ActivityType.UNKNOWN,
            confidence=0.0,
        ),
        None,
    )

def extract_event_type(text: str) -> EventTypeValue:
    text_lower = text.lower()

    # "not started" must not be classified as START.
    if re.search(r"\bnot\s+started\b", text_lower):
        return EventTypeValue(
            value=EventType.UNKNOWN,
            confidence=0.0,
        )

    # 100% complete must be classified as FINISH, not PROGRESS.
    if re.search(
        r"\b100\s*%\s*(?:complete|completed)?\b",
        text_lower,
    ):
        return EventTypeValue(
            value=EventType.FINISH,
            confidence=0.95,
        )

    # Percentage mentioned means the work is in progress.
    # Example: "10% complete", "60% completed", "50 percent complete"
    if re.search(
        r"\b\d+(?:\.\d+)?\s*%\s*(?:complete|completed)?\b",
        text_lower,
    ):
        return EventTypeValue(
            value=EventType.PROGRESS,
            confidence=0.88,
        )

    # Spelled-out or numeric percentage like "50 percent complete" or
    # "fifty percent complete" = PROGRESS
    if re.search(
        r"\b(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|"
        r"ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
        r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
        r"eighty|ninety|hundred)\s+percent\b",
        text_lower,
    ):
        return EventTypeValue(
            value=EventType.PROGRESS,
            confidence=0.88,
        )

    # "half complete" = PROGRESS
    if re.search(r"\bhalf\b", text_lower):
        return EventTypeValue(
            value=EventType.PROGRESS,
            confidence=0.88,
        )

    # "almost complete" / "almost finished" = PROGRESS (not FINISH)
    if re.search(r"\balmost\b", text_lower):
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


def _find_percentage_value(text: str) -> Optional[float]:
    """Extract a percentage number from text. Handles %, 'percent', 'per cent',
    and 'half'. Returns None if no percentage is found or the value is invalid."""
    text_lower = text.lower()

    # Handle "half" as 50%.
    if re.search(r"\bhalf\b", text_lower):
        return 50.0

    # Match numeric percentage with % symbol or spelled-out variants.
    # Use negative lookbehind to prevent matching after a minus sign.
    match = re.search(
        r"(?<!\-)\b(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)(?!\w)",
        text_lower,
    )
    if match:
        return float(match.group(1))

    return None


def extract_progress(
    text: str,
    event_type: EventTypeValue,
) -> ExtractedNumericValue:

    percentage_value = _find_percentage_value(text)

    if percentage_value is not None:
        if percentage_value < 0:
            # Negative percentages must never be stored as valid progress.
            return ExtractedNumericValue(
                value=None,
                confidence=0.0,
            )
        if percentage_value > 100:
            # Percentages above 100 must not be stored as valid progress.
            return ExtractedNumericValue(
                value=None,
                confidence=0.0,
            )
        if 0.0 <= percentage_value <= 100.0:
            return ExtractedNumericValue(
                value=percentage_value,
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
    activity_type, activity_type_source = extract_activity_type(report.normalized_text)
    event_type = extract_event_type(report.normalized_text)
    progress = extract_progress(report.normalized_text, event_type)

    extraction_flags = []

    if not equipment_tags:
        extraction_flags.append("NO_EQUIPMENT_TAG")

    if not locations:
        extraction_flags.append("NO_LOCATION")

    if activity_type.value == ActivityType.UNKNOWN:
        extraction_flags.append("UNKNOWN_ACTIVITY_TYPE")
    elif activity_type_source:
        # Resolved via a fallback layer rather than the exact-match layer --
        # worth surfacing for audit trails / human-review explanations, and
        # for Module 5 to gate AUTO_MATCH eligibility on (this value is a
        # guess, not a confident exact match).
        extraction_flags.append(activity_type_source)

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