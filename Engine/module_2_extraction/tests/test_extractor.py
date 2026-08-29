from shared.constants import ActivityType, EventType
from shared.schemas import NormalizedReport

from Engine.module_2_extraction.extractor import extract_information


def make_report(text: str) -> NormalizedReport:
    return NormalizedReport(
        report_id="TEST-001",
        original_text=text,
        normalized_text=text,
        normalization_flags=[],
    )


def test_normal_extraction():
    report = make_report(
        "Excavate work for F-101 10% complete at Pump Area A."
    )

    result = extract_information(report)

    assert result.report_id == "TEST-001"
    assert result.normalized_text == report.normalized_text
    assert result.equipment_tags[0].value == "F-101"
    assert result.locations[0].value == "Pump Area A"
    assert result.activity_type.value == ActivityType.EXCAVATE
    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value == 10.0


def test_abbreviation_case():
    report = make_report(
        "P-888 installation completed in Unit 2."
    )

    result = extract_information(report)

    assert result.equipment_tags[0].value == "P-888"
    assert result.locations[0].value == "Unit 2"
    assert result.activity_type.value == ActivityType.INSTALL
    assert result.event_type.value == EventType.FINISH
    assert result.progress.value == 100.0


def test_noisy_case():
    report = make_report(
        "today!! SP-101 welding 60% complete @ Pipe Rack"
    )

    result = extract_information(report)

    assert result.equipment_tags[0].value == "SP-101"
    assert result.locations[0].value == "Pipe Rack"
    assert result.activity_type.value == ActivityType.WELD
    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value == 60.0


def test_incomplete_case():
    report = make_report(
        "Work ongoing at Area B."
    )

    result = extract_information(report)

    assert result.equipment_tags == []
    assert result.locations[0].value == "Area B"
    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value is None
    assert "NO_EQUIPMENT_TAG" in result.extraction_flags
    assert "PROGRESS_UNDETERMINED" in result.extraction_flags


def test_ambiguous_activity_case():
    report = make_report(
        "SP-101 welding and erection ongoing."
    )

    result = extract_information(report)

    assert result.activity_type.value == ActivityType.UNKNOWN
    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value is None
    assert "UNKNOWN_ACTIVITY_TYPE" in result.extraction_flags


def test_unmatched_case():
    report = make_report(
        "General site activity observed."
    )

    result = extract_information(report)

    assert result.equipment_tags == []
    assert result.locations == []
    assert result.activity_type.value == ActivityType.UNKNOWN
    assert result.event_type.value == EventType.UNKNOWN
    assert result.progress.value is None


def test_multiple_equipment_tags():
    report = make_report(
        "Welding started on F-101 and P-888 at Pipe Rack."
    )

    result = extract_information(report)

    values = [entity.value for entity in result.equipment_tags]

    assert "F-101" in values
    assert "P-888" in values
    assert len(values) == 2


def test_started_means_zero_progress():
    report = make_report(
        "Installation started on P-888 at Pump Area A."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.START
    assert result.progress.value == 0.0


def test_completed_means_full_progress():
    report = make_report(
        "Welding completed on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.FINISH
    assert result.progress.value == 100.0


def test_progress_is_not_guessed():
    report = make_report(
        "Welding ongoing on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value is None

