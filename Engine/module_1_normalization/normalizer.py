"""Rule-based text normalization for Module 1."""

from __future__ import annotations

import re
from shared.schemas import RawReportInput, NormalizedReport


# Conservative, domain-specific replacements only.  These rules normalize
# surface form; they do not classify events, infer progress, or extract entities.
_TYPO_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcompletd\b", re.IGNORECASE), "completed"),
    (re.compile(r"\binspec\b", re.IGNORECASE), "inspect"),
    (re.compile(r"\binstalation\b", re.IGNORECASE), "installation"),
    (re.compile(r"\bexcavateion\b", re.IGNORECASE), "excavation"),
    (re.compile(r"\bweldng\b", re.IGNORECASE), "welding"),
    (re.compile(r"\berction\b", re.IGNORECASE), "erection"),
)

_ABBREVIATION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfit\s*up\b", re.IGNORECASE), "fit-up"),
    (re.compile(r"\bhydro\s*test\b", re.IGNORECASE), "hydrotest"),
)

_LOCATION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bPA[\s-]*A\b", re.IGNORECASE), "Pump Area A"),
    (re.compile(r"\bpump(?:\s+area)?\s+A\b", re.IGNORECASE), "Pump Area A"),
    (re.compile(r"\bPA[\s-]*B\b", re.IGNORECASE), "Pump Area B"),
    (re.compile(r"\bpump(?:\s+area)?\s+B\b", re.IGNORECASE), "Pump Area B"),
    (re.compile(r"\bPR[\s-]*C\b", re.IGNORECASE), "Process Area C"),
    (re.compile(r"\bprocess(?:\s+area)?\s+C\b", re.IGNORECASE), "Process Area C"),
    (re.compile(r"\bUT[\s-]*A\b", re.IGNORECASE), "Utility Area"),
    (re.compile(r"\bUtilities\b", re.IGNORECASE), "Utility Area"),
)

# Examples: F 101, f101, P 102, sp101 -> F-101, F-101, P-102, SP-101.
# A word boundary on both sides prevents touching percentages or ordinary words.
_KNOWN_TAG_PREFIXES = ("SP", "PT", "FT", "MCC", "LP", "HL", "CT", "T", "F", "P")  # or load from domain_context.csv
_prefix_alt = "|".join(sorted(_KNOWN_TAG_PREFIXES, key=len, reverse=True))
_EQUIPMENT_TAG_RE = re.compile(rf"\b({_prefix_alt})[\s-]*(\d{{3,4}})\b", re.IGNORECASE)


def _apply_rules(
    text: str,
    rules: tuple[tuple[re.Pattern[str], str], ...],
) -> tuple[str, bool]:
    changed = False
    for pattern, replacement in rules:
        text, count = pattern.subn(replacement, text)
        changed = changed or count > 0
    return text, changed


def _collapse_whitespace(text: str) -> tuple[str, bool]:
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\s*\n\s*", " ", cleaned)
    cleaned = cleaned.strip()
    return cleaned, cleaned != text


def normalize_report(report: RawReportInput) -> NormalizedReport:
    """Normalize one raw field report without extracting or inventing facts.

    The function preserves ``report.report_id`` verbatim and copies
    ``report.raw_text`` byte-for-byte into ``original_text``. Only the
    ``normalized_text`` working copy is modified.
    """

    original_text = report.raw_text
    normalized_text = original_text
    flags: list[str] = []

    normalized_text, changed = _apply_rules(normalized_text, _TYPO_RULES)
    if changed:
        flags.append("typo_corrected")

    normalized_text, changed = _apply_rules(normalized_text, _ABBREVIATION_RULES)
    if changed:
        flags.append("abbreviation_expanded")

    normalized_text, changed = _apply_rules(normalized_text, _LOCATION_RULES)
    if changed:
        flags.append("location_alias_expanded")

    before_tags = normalized_text
    normalized_text = _EQUIPMENT_TAG_RE.sub(
        lambda m: f"{m.group(1).upper()}-{m.group(2)}",
        normalized_text,
    )
    if normalized_text != before_tags:
        flags.append("equipment_tag_standardized")

    normalized_text, changed = _collapse_whitespace(normalized_text)
    if changed:
        flags.append("whitespace_normalized")

    return NormalizedReport(
        report_id=report.report_id,
        original_text=original_text,
        normalized_text=normalized_text,
        normalization_flags=flags,
    )
