# Module 2 — Information Extraction

## Purpose

Module 2 converts a `NormalizedReport` into an `ExtractedReport`.

It extracts:

- equipment tags
- locations
- activity type
- event type
- progress percentage
- extraction flags

This module does not normalize text, retrieve schedule candidates, rank activities, make decisions, or use ground truth.

## Input

`NormalizedReport`

Fields used:

- `report_id`
- `normalized_text`

## Output

`ExtractedReport`

Fields produced:

- `report_id`
- `normalized_text`
- `equipment_tags`
- `locations`
- `activity_type`
- `event_type`
- `progress`
- `extraction_flags`

## Configuration

Activity aliases are stored in:

`config/activity_aliases.json`

Locations are stored in:

`config/locations.json`

The extraction logic uses the official enums from:

`shared.constants`

and official Pydantic models from:

`shared.schemas`

## Core Function

```python
extract_information(report: NormalizedReport) -> ExtractedReport