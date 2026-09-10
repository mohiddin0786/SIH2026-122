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


def test_not_started_is_not_start_event():
    """'not started' must not be classified as START; should be UNKNOWN."""
    report = make_report(
        "Installation not started on P-888 at Pump Area A."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.UNKNOWN
    assert result.progress.value is None
    assert "UNKNOWN_EVENT_TYPE" in result.extraction_flags


def test_100_percent_complete_is_finish():
    """'100% complete' must be classified as FINISH, not PROGRESS."""
    report = make_report(
        "Welding 100% complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.FINISH
    assert result.progress.value == 100.0
    assert "PROGRESS_UNDETERMINED" not in result.extraction_flags


def test_50_percent_complete_is_progress():
    """'50% complete' must be classified as PROGRESS with progress 50.0."""
    report = make_report(
        "Welding 50% complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value == 50.0


def test_50_percent_spelled_out_is_progress():
    """'50 percent complete' must be classified as PROGRESS with progress 50.0."""
    report = make_report(
        "Welding 50 percent complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value == 50.0


def test_half_complete_is_progress_fifty():
    """'half complete' must be classified as PROGRESS with progress 50.0."""
    report = make_report(
        "Welding half complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value == 50.0


def test_99_5_percent_complete_is_progress():
    """'99.5% complete' must be classified as PROGRESS with progress 99.5."""
    report = make_report(
        "Welding 99.5% complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value == 99.5


def test_almost_complete_is_progress_none():
    """'almost complete' must be PROGRESS but progress None."""
    report = make_report(
        "Welding almost complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value is None
    assert "PROGRESS_UNDETERMINED" in result.extraction_flags


def test_negative_percentage_not_extracted():
    """'-10% complete' must not produce valid progress."""
    report = make_report(
        "Welding -10% complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value is None
    assert "PROGRESS_UNDETERMINED" in result.extraction_flags


def test_percentage_above_100_not_extracted():
    """'120% complete' must not be stored as valid progress."""
    report = make_report(
        "Welding 120% complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value is None
    assert "PROGRESS_UNDETERMINED" in result.extraction_flags


def test_zero_percent_complete_is_progress_zero():
    """'0% complete' must be classified as PROGRESS with progress 0.0."""
    report = make_report(
        "Welding 0% complete on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert result.event_type.value == EventType.PROGRESS
    assert result.progress.value == 0.0


def test_unit_location_extraction():
    """'Unit 2' must be extracted as a location."""
    report = make_report(
        "P-888 installation completed in Unit 2."
    )

    result = extract_information(report)

    assert any(loc.value == "Unit 2" for loc in result.locations)


def test_area_location_extraction():
    """'Area B' must be extracted as a location."""
    report = make_report(
        "Work ongoing at Area B."
    )

    result = extract_information(report)

    assert any(loc.value == "Area B" for loc in result.locations)


def test_zone_location_extraction():
    """'Zone 4' must be extracted as a location."""
    report = make_report(
        "Insulation work 50% complete in Zone 4."
    )

    result = extract_information(report)

    assert any(loc.value == "Zone 4" for loc in result.locations)


def test_block_location_extraction():
    """'Block C' must be extracted as a location."""
    report = make_report(
        "Painting started on T-201 at Block C."
    )

    result = extract_information(report)

    assert any(loc.value == "Block C" for loc in result.locations)


def test_pipe_rack_location():
    """'Pipe Rack' must be extracted as a configured location."""
    report = make_report(
        "Welding completed on F-101 at Pipe Rack."
    )

    result = extract_information(report)

    assert any(loc.value == "Pipe Rack" for loc in result.locations)


def test_cables_routed_extracts_pull_cable():
    """'cables routed' must be extracted as PULL_CABLE."""
    report = make_report(
        "Electrical update: cables routed of CT-101 60% complete at Pump Area A."
    )
    result = extract_information(report)
    assert result.activity_type.value == ActivityType.PULL_CABLE


def test_cables_terminated_extracts_terminate_cable():
    """'cables terminated' must be extracted as TERMINATE_CABLE."""
    report = make_report(
        "CT-101 cables terminated 60% complete at Pump Area A."
    )
    result = extract_information(report)
    assert result.activity_type.value == ActivityType.TERMINATE_CABLE


def test_generic_nouns_do_not_extract_install():
    """Generic object nouns ('electrical', 'cable', 'tray') alone must NOT exact-match INSTALL."""
    from Engine.module_2_extraction.extractor import _extract_activity_type_exact
    for noun in ["electrical", "cable", "tray"]:
        matches = _extract_activity_type_exact(f"update for {noun} work at area a.")
        assert "INSTALL" not in matches


def test_joint_preparation_extracts_fit_up():
    """'joint preparation' and 'joint prep' must extract as FIT_UP activity type."""
    r1 = make_report("SP302 joint preparation completed in Utility Area.")
    res1 = extract_information(r1)
    assert res1.activity_type.value == ActivityType.FIT_UP

    r2 = make_report("sp-103 joint prep 50% complete at PA B.")
    res2 = extract_information(r2)
    assert res2.activity_type.value == ActivityType.FIT_UP



