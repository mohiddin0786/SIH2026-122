"""Generate Data/domain_context.json from Data/schedule_master_v1.csv.

Single source of truth for domain vocabulary (equipment tag prefixes,
locations, and activity-type synonyms) that Module 1 (normalizer) and
Module 2 (extractor) both need. Run this whenever schedule_master_v1.csv
changes; it is NOT part of the per-report pipeline and does not touch
shared/schemas.py.

Usage:
    python scripts/generate_domain_context.py
    python scripts/generate_domain_context.py --schedule path/to/other.csv --out path/to/out.json

Also writes/overwrites Engine/module_2_extraction/config/locations.json
directly (via --write-locations, on by default) so the extractor needs no
code change to pick up new locations. Set --no-write-locations to skip
that and only emit domain_context.json.

ACTIVITY-TYPE VOCABULARY MINING
--------------------------------
activity_aliases.json used to be a hand-typed, static word list per
ActivityType. That silently fails on any real report phrasing the list's
author didn't anticipate (measured: ~40% UNKNOWN on raw_reports_v1.csv
before this change). schedule_master_v1.csv has no activity_type column,
so we can't mine it directly the way we mine locations/equipment. Instead:

  1. Load the CURRENT activity_aliases.json as a seed classifier.
  2. For each schedule row, classify activity_name + activity_description
     against that seed (same word-boundary rule extractor.py uses) to
     bucket the row into exactly one ActivityType. Rows matching 0 or 2+
     seed aliases are skipped and printed as warnings -- we do not guess.
  3. From each bucket's matched rows, mine additional significant words
     out of activity_name + activity_description (stopwords removed).
  4. Union the mined words into the existing seed list per bucket --
     this only ever GROWS the list, never removes a hand-curated word.
  5. Write the merged result into domain_context.json (for inspection)
     AND overwrite Engine/module_2_extraction/config/activity_aliases.json
     the same way locations.json is overwritten today, so extractor.py
     needs no code change to benefit.

This is still a versioned config file -- review the printed "added
words" diff before committing, same as you would any generated file.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEDULE = REPO_ROOT / "Data" / "schedule_master_v1.csv"
DEFAULT_OUT = REPO_ROOT / "Data" / "domain_context.json"
DEFAULT_LOCATIONS_JSON = REPO_ROOT / "Engine" / "module_2_extraction" / "config" / "locations.json"
DEFAULT_ACTIVITY_ALIASES_JSON = REPO_ROOT / "Engine" / "module_2_extraction" / "config" / "activity_aliases.json"

# Matches a leading letter-prefix on an equipment tag, e.g. "SP-101" -> "SP",
# "F101" -> "F". Mirrors the tag shape used throughout schedule_master_v1.csv.
_TAG_PREFIX_RE = re.compile(r"^([A-Za-z]+)-?\d")

# Small stopword list for activity-name/description mining. Deliberately
# short and domain-neutral -- we'd rather under-filter (extra noise word
# that fuzzy/semantic matching shrugs off) than over-filter (accidentally
# drop a real verb).
_STOPWORDS = {
    "a", "an", "the", "for", "and", "of", "to", "in", "at", "on", "with",
    "is", "are", "was", "were", "be", "being", "been", "this", "that",
    "final", "preliminary", "work", "check", "checks",
}

_WORD_RE = re.compile(r"[a-z]+")


def extract_prefixes(schedule_path: Path) -> list[str]:
    prefixes: dict[str, int] = {}
    unparsed: list[str] = []

    with schedule_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tag = (row.get("equipment_tag") or "").strip()
            if not tag:
                continue
            match = _TAG_PREFIX_RE.match(tag)
            if match:
                prefix = match.group(1).upper()
                prefixes[prefix] = prefixes.get(prefix, 0) + 1
            else:
                unparsed.append(tag)

    if unparsed:
        print(f"WARNING: {len(unparsed)} equipment_tag values did not match the "
              f"expected <letters><digits> shape and were skipped: {unparsed[:10]}"
              + (" ..." if len(unparsed) > 10 else ""))

    # Longest-first so the regex built from these tries multi-letter
    # prefixes (e.g. "TT", "SP") before single-letter ones (e.g. "T").
    return sorted(prefixes, key=lambda p: (-len(p), p))


def extract_locations(schedule_path: Path) -> list[str]:
    locations: set[str] = set()
    with schedule_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc = (row.get("location") or "").strip()
            if loc:
                locations.add(loc)
    # Longest-first, matching the sort extract_locations() in extractor.py
    # already does at runtime -- harmless duplication, keeps the emitted
    # file readable/diffable on its own.
    return sorted(locations, key=lambda l: (-len(l), l))


def _load_seed_aliases(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        raise SystemExit(
            f"Seed activity_aliases.json not found at {path}. This script "
            "extends the existing seed file rather than inventing categories "
            "from scratch -- make sure it exists before running."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _classify_row(text: str, seed_aliases: dict[str, list[str]]) -> str | None:
    """Same word-boundary logic as extractor.py's exact-match layer.
    Returns the single matching ActivityType key, or None if 0 or 2+
    seed aliases matched (caller is responsible for warning on None)."""
    text_lower = text.lower()
    matched = []
    for activity_name, aliases in seed_aliases.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias.lower())}\b", text_lower):
                matched.append(activity_name)
                break
    unique = list(dict.fromkeys(matched))
    return unique[0] if len(unique) == 1 else None


def mine_activity_vocabulary(
    schedule_path: Path,
    seed_aliases_path: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Returns (merged_aliases, added_words_per_bucket) for reporting."""
    seed_aliases = _load_seed_aliases(seed_aliases_path)
    buckets: dict[str, list[str]] = {k: [] for k in seed_aliases}
    unclassified: list[str] = []

    with schedule_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("activity_name") or "").strip()
            desc = (row.get("activity_description") or "").strip()
            combined = f"{name} {desc}".strip()
            if not combined:
                continue
            bucket = _classify_row(combined, seed_aliases)
            if bucket is None:
                unclassified.append(combined)
                continue
            buckets[bucket].append(combined)

    if unclassified:
        print(f"WARNING: {len(unclassified)} schedule rows matched 0 or 2+ seed "
              f"activity aliases and were skipped from vocabulary mining "
              f"(seed list may need a human look at these): {unclassified[:5]}"
              + (" ..." if len(unclassified) > 5 else ""))

    # Mine raw candidate words per bucket first, without touching the seed
    # yet -- we need to see word usage ACROSS buckets before deciding what's
    # discriminative.
    raw_mined: dict[str, set[str]] = {}
    for activity_name, rows_text in buckets.items():
        mined_words: set[str] = set()
        for text in rows_text:
            for word in _WORD_RE.findall(text.lower()):
                if len(word) < 3 or word in _STOPWORDS:
                    continue
                mined_words.add(word)
        raw_mined[activity_name] = mined_words

    # Generic domain nouns ("pump", "piping", "complete", "work"...) show up
    # in MANY buckets' descriptions and are not discriminative -- adding them
    # as an alias for one bucket would make that bucket false-positive-match
    # any report mentioning the noun regardless of actual activity type. Only
    # keep a mined word for a bucket if it appears in that bucket's rows and
    # NO other bucket's rows.
    word_bucket_counts: dict[str, int] = {}
    for words in raw_mined.values():
        for w in words:
            word_bucket_counts[w] = word_bucket_counts.get(w, 0) + 1

    merged: dict[str, list[str]] = {}
    added: dict[str, list[str]] = {}
    dropped_generic: dict[str, list[str]] = {}

    for activity_name, mined_words in raw_mined.items():
        existing = set(w.lower() for w in seed_aliases.get(activity_name, []))
        discriminative = {w for w in mined_words if word_bucket_counts[w] == 1}
        generic = mined_words - discriminative

        new_words = sorted(discriminative - existing)
        merged_list = sorted(existing | discriminative)

        merged[activity_name] = merged_list
        if new_words:
            added[activity_name] = new_words
        if generic:
            dropped_generic[activity_name] = sorted(generic)

    if dropped_generic:
        print("  activity aliases -- generic words seen in 2+ buckets, skipped as non-discriminative:")
        all_generic = sorted(set(w for words in dropped_generic.values() for w in words))
        print(f"    {all_generic}")

    return merged, added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE,
                         help="Path to schedule_master_v1.csv")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                         help="Path to write domain_context.json")
    parser.add_argument("--locations-json", type=Path, default=DEFAULT_LOCATIONS_JSON,
                         help="Path to Module 2's locations.json")
    parser.add_argument("--activity-aliases-json", type=Path, default=DEFAULT_ACTIVITY_ALIASES_JSON,
                         help="Path to Module 2's activity_aliases.json (read as seed, then overwritten)")
    parser.add_argument("--no-write-locations", action="store_true",
                         help="Skip overwriting locations.json; only emit domain_context.json")
    parser.add_argument("--no-write-activity-aliases", action="store_true",
                         help="Skip overwriting activity_aliases.json; only emit domain_context.json")
    args = parser.parse_args()

    if not args.schedule.exists():
        raise SystemExit(f"Schedule file not found: {args.schedule}")

    prefixes = extract_prefixes(args.schedule)
    locations = extract_locations(args.schedule)
    activity_aliases, added_words = mine_activity_vocabulary(
        args.schedule, args.activity_aliases_json
    )

    domain_context = {
        "_generated_from": str(args.schedule.relative_to(REPO_ROOT)) if args.schedule.is_relative_to(REPO_ROOT) else str(args.schedule),
        "_note": "Auto-generated by scripts/generate_domain_context.py. Do not hand-edit; re-run the script instead.",
        "equipment_tag_prefixes": prefixes,
        "locations": locations,
        "activity_type_aliases": activity_aliases,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(domain_context, f, indent=2)
        f.write("\n")
    print(f"Wrote {args.out} — {len(prefixes)} equipment prefixes, {len(locations)} locations, "
          f"{sum(len(v) for v in activity_aliases.values())} activity-alias words")
    print(f"  prefixes: {prefixes}")
    print(f"  locations: {locations}")
    if added_words:
        print("  activity aliases -- newly mined words (review before committing):")
        for activity_name, words in added_words.items():
            print(f"    {activity_name}: +{words}")
    else:
        print("  activity aliases -- no new words mined this run.")

    if not args.no_write_locations:
        args.locations_json.parent.mkdir(parents=True, exist_ok=True)
        with args.locations_json.open("w", encoding="utf-8") as f:
            json.dump({"locations": locations}, f, indent=2)
            f.write("\n")
        print(f"Wrote {args.locations_json} (Module 2 locations config, regenerated from schedule)")

    if not args.no_write_activity_aliases:
        args.activity_aliases_json.parent.mkdir(parents=True, exist_ok=True)
        with args.activity_aliases_json.open("w", encoding="utf-8") as f:
            json.dump(activity_aliases, f, indent=2)
            f.write("\n")
        print(f"Wrote {args.activity_aliases_json} (Module 2 activity-aliases config, regenerated from schedule)")


if __name__ == "__main__":
    main()