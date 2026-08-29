"""Equipment/location retrieval scores must not use substring fuzzy on tags."""

from Engine.module_3_candidate.retriever import (
    _equipment_match_score,
    _location_match_score,
)


def test_equipment_normalized_forms_match():
    assert _equipment_match_score("sp 101", "SP-101") == 1.0
    assert _equipment_match_score("SP101", "SP-101") == 1.0


def test_equipment_substring_tag_is_not_a_match():
    assert _equipment_match_score("SP-101", "P-101") == 0.0
    assert _equipment_match_score("SP-101", "SP-999") == 0.0


def test_location_area_suffix_is_not_a_match():
    assert _location_match_score("Pump Area A", "Pump Area A") == 1.0
    assert _location_match_score("Pump Area A", "Pump Area B") == 0.0
