"""
Engine/module_4_matching/test/test_activity_matcher.py

Regression tests for activity_matcher boundary matching and synonym scoring.
"""

from __future__ import annotations

import pytest
from shared.constants import ActivityType

from module_4_matching.activity_matcher import score_activity
from module_4_matching.config import DEFAULT_ACTIVITY_SYNONYMS


def test_weld_matches_weld_piping_spool():
    """'weld' synonym should match 'Weld piping spool' with score 1.0."""
    result = score_activity(
        ActivityType.WELD,
        "Weld piping spool",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.computable is True
    assert result.score == 1.0
    assert result.contradiction is False
    assert any("WELD -> 'weld'" in exp for exp in result.explanation)


def test_weld_does_not_incorrectly_match_inspect_welds():
    """'weld' synonym should NOT make an INSPECT activity ('Inspect welds for piping spool')
    an exact WELD activity match (score should be < 1.0, not 1.0)."""
    result_weld = score_activity(
        ActivityType.WELD,
        "Inspect welds for piping spool",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result_weld.score < 0.999, "WELD should not give 1.0 match on 'Inspect welds for piping spool'"

    result_inspect = score_activity(
        ActivityType.INSPECT,
        "Inspect welds for piping spool",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result_inspect.score == 1.0, "INSPECT should match 'Inspect welds for piping spool' with score 1.0"


def test_multi_word_aliases_and_hyphenated_terms():
    """Verify multi-word and hyphenated synonyms match correctly."""
    cases = [
        (ActivityType.FIT_UP, "Piping fit-up work"),
        (ActivityType.FIT_UP, "Piping fit up work"),
        (ActivityType.HYDROTEST, "Hydrostatic pressure test for line A"),
        (ActivityType.PULL_CABLE, "Pull cable in unit 1"),
        (ActivityType.CAST, "Foundation concrete pour"),
        (ActivityType.INSTALL, "Equipment installation at area B"),
    ]
    for act_type, cand_name in cases:
        result = score_activity(
            act_type,
            cand_name,
            DEFAULT_ACTIVITY_SYNONYMS,
            fuzzy_match_floor=40,
        )
        assert result.score == 1.0, f"Expected 1.0 score for {act_type} in '{cand_name}'"


def test_activity_matcher_edge_cases():
    """Verify handling of unknown types, empty names, and missing synonyms."""
    res1 = score_activity("UNKNOWN", "Weld piping spool", DEFAULT_ACTIVITY_SYNONYMS, 40)
    assert res1.score == 0.0
    assert res1.computable is False

    res2 = score_activity(ActivityType.WELD, "", DEFAULT_ACTIVITY_SYNONYMS, 40)
    assert res2.score == 0.0
    assert res2.computable is False

    res3 = score_activity("NON_EXISTENT", "Weld piping spool", DEFAULT_ACTIVITY_SYNONYMS, 40)
    assert res3.score == 0.0
    assert res3.computable is False


def test_pull_cables_maps_to_pull_cable():
    """'pull cables' must correctly identify PULL_CABLE activity type."""
    result = score_activity(
        ActivityType.PULL_CABLE,
        "Pull cables through CT-301",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.score == 1.0, f"Expected 1.0 for 'pull cables' in PULL_CABLE, got {result.score}"
    assert result.computable is True
    assert any("PULL_CABLE" in exp for exp in result.explanation)


def test_activity_matcher_fuzzy_prevents_false_positive():
    """Fuzzy matching must not produce false positives like 'cable tray'
    matching 'pull cable' for PULL_CABLE activity type.

    'Install cable tray CT-301' should NOT get a high activity_score
    for PULL_CABLE because 'cable tray' is not a valid pull cable term.
    """
    result = score_activity(
        ActivityType.PULL_CABLE,
        "Install cable tray CT-301",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    # With the word-overlap guardrail, 'cable tray' should not fuzzy-match
    # 'pull cable' because 'pull' is not in the window tokens
    assert result.score < 0.999, f"Expected false positive prevention, got score {result.score}"


def test_cable_pulling_still_works():
    """'cable pulling' must still correctly identify PULL_CABLE."""
    result = score_activity(
        ActivityType.PULL_CABLE,
        "Cable pulling completed in UT-A.",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.score == 1.0
    assert result.computable is True


def test_cable_pull_still_works():
    """'cable pull' must identify PULL_CABLE (fuzzy match on reversed word order)."""
    result = score_activity(
        ActivityType.PULL_CABLE,
        "Cable pull work completed.",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.score > 0.0
    assert result.computable is True
    assert result.score < 1.0  # reversed word order gives partial fuzzy match


def test_pulling_cable_still_works():
    """'pulling cable' must identify PULL_CABLE (fuzzy match on reversed word order)."""
    result = score_activity(
        ActivityType.PULL_CABLE,
        "Pulling cable work done.",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.score > 0.0
    assert result.computable is True
    assert result.score < 1.0  # reversed word order gives partial fuzzy match


# ---------------------------------------------------------------------------
# Regression: INSTALL vs FIT_UP tie-break fix (2026-09-09)
#
# Root cause: bare "fit" was in INSTALL synonyms and matched via \bfit\b on
# FIT_UP candidate names (e.g. "Perform fit-up for piping spool SP-101").
# The regex \bfit\b matches "fit" inside "fit-up" because "-" is a word
# boundary. This caused both INSTALL and FIT_UP candidates to receive
# activity_score=1.0, creating an INSUFFICIENT_GAP block that sent 8 correct
# INSTALL reports to HUMAN_REVIEW instead of AUTO_MATCH.
#
# Affected reports: RPT-0087, RPT-0088, RPT-0286, RPT-0316, RPT-0442,
#                   RPT-0472, RPT-0598, RPT-0627
#
# Fix: removed "fit" from INSTALL synonyms; kept it only under FIT_UP.
# ---------------------------------------------------------------------------


def test_install_does_not_match_fitup_candidate_name():
    """INSTALL type must NOT score 1.0 against a FIT_UP candidate name.

    Realistic scenario from RPT-0087: "PA A: SP101 placed done"
    extracted as INSTALL. Should differentiate between:
      C1: "Install piping spool SP-101"            -> activity_score=1.0
      C2: "Perform fit-up for piping spool SP-101" -> activity_score<1.0

    Previously bare "fit" in INSTALL synonyms caused C2 to also score 1.0
    because \\bfit\\b matches "fit" inside "fit-up". This created an
    INSUFFICIENT_GAP block preventing AUTO_MATCH.
    """
    result = score_activity(
        ActivityType.INSTALL,
        "Perform fit-up for piping spool SP-101",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.score < 0.999, (
        f"INSTALL should NOT score 1.0 on FIT_UP candidate name, got {result.score}. "
        "Regression: bare 'fit' was re-added to INSTALL synonyms."
    )


def test_install_still_matches_install_candidate_names():
    """INSTALL type must still score 1.0 against real INSTALL candidate names.

    Verifies that removing "fit" from INSTALL synonyms did not break
    legitimate INSTALL scoring. Uses the exact candidate names from the 8
    affected benchmark reports.
    """
    install_candidate_names = [
        "Install piping spool SP-101",   # RPT-0087, RPT-0088, RPT-0286
        "Install piping spool SP-103",   # RPT-0316
        "Install piping spool SP-201",   # RPT-0442
        "Install piping spool SP-202",   # RPT-0472
        "Install piping spool SP-301",   # RPT-0598
        "Install piping spool SP-302",   # RPT-0627
        "Install pump P-101",
        "Install cable tray CT-101",
        "Equipment installation at area B",
    ]
    for name in install_candidate_names:
        result = score_activity(
            ActivityType.INSTALL,
            name,
            DEFAULT_ACTIVITY_SYNONYMS,
            fuzzy_match_floor=40,
        )
        assert result.score == 1.0, (
            f"INSTALL should score 1.0 on '{name}', got {result.score}"
        )


def test_fitup_still_matches_fitup_candidate_names():
    """FIT_UP type must still score 1.0 against FIT_UP candidate names.

    "fit" remains in FIT_UP synonyms; this confirms it was not accidentally
    removed from FIT_UP too.
    """
    fitup_candidate_names = [
        "Perform fit-up for piping spool SP-101",
        "Perform fit-up for piping spool SP-103",
        "Perform fit-up for piping spool SP-201",
        "Perform fit-up for piping spool SP-202",
        "Perform fit-up for piping spool SP-301",
        "Perform fit-up for piping spool SP-302",
    ]
    for name in fitup_candidate_names:
        result = score_activity(
            ActivityType.FIT_UP,
            name,
            DEFAULT_ACTIVITY_SYNONYMS,
            fuzzy_match_floor=40,
        )
        assert result.score == 1.0, (
            f"FIT_UP should score 1.0 on '{name}', got {result.score}"
        )


def test_install_vs_fitup_activity_scores_are_differentiated():
    """Full disambiguation test: for an INSTALL-typed report, the INSTALL
    candidate must clearly outscore the FIT_UP candidate.

    This directly models all 8 INSUFFICIENT_GAP cases. Before the fix both
    candidates scored 1.0 (gap=0). After the fix INSTALL=1.0, FIT_UP<1.0,
    creating a meaningful gap that allows AUTO_MATCH.
    """
    install_score = score_activity(
        ActivityType.INSTALL,
        "Install piping spool SP-101",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    ).score

    fitup_score = score_activity(
        ActivityType.INSTALL,
        "Perform fit-up for piping spool SP-101",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    ).score

    assert install_score == 1.0, f"INSTALL candidate should score 1.0, got {install_score}"
    assert fitup_score < 0.999, (
        f"FIT_UP candidate should score <1.0 under INSTALL type, got {fitup_score}. "
        "Regression: bare 'fit' was re-added to INSTALL synonyms."
    )
    assert install_score > fitup_score, (
        f"INSTALL score ({install_score}) must exceed FIT_UP score ({fitup_score})."
    )


def test_install_placed_synonym_still_works():
    """Verify 'placed' synonym for INSTALL still works after the fix.

    RPT-0087: "SP101 placed done", RPT-0627: "SP 302 placed 60% complete"
    all use "placed" which must still map to INSTALL.
    """
    result = score_activity(
        ActivityType.INSTALL,
        "Install piping spool SP-101",  # candidate name contains "install"
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.score == 1.0

    # Also verify the report text keywords would drive INSTALL extraction
    # (handled by module 2, but we check the synonym table is consistent)
    assert "placed" in DEFAULT_ACTIVITY_SYNONYMS["INSTALL"], (
        "'placed' must remain in INSTALL synonyms for extraction to work on "
        "reports like 'SP101 placed done'"
    )
    assert "fit" not in DEFAULT_ACTIVITY_SYNONYMS["INSTALL"], (
        "bare 'fit' must NOT be in INSTALL synonyms (causes FIT_UP false match)"
    )
    assert "fit" in DEFAULT_ACTIVITY_SYNONYMS["FIT_UP"], (
        "'fit' must remain in FIT_UP synonyms"
    )


# ---------------------------------------------------------------------------
# Regression: TERMINATE_CABLE candidate name matching fix (2026-09-09)
#
# Root cause: DEFAULT_ACTIVITY_SYNONYMS["TERMINATE_CABLE"] was missing
# "terminate cables" (plural cables). Candidate names like
# "Terminate cables in CT-101" scored c1_act=0.0, causing AMBIGUOUS_NO_ACTIVITY
# and INSUFFICIENT_GAP blocks for 7 benchmark reports.
# ---------------------------------------------------------------------------


def test_terminate_cables_matches_candidate_name():
    """'Terminate cables in CT-101' candidate name must score 1.0 under TERMINATE_CABLE.

    Verifies fix for RPT-0157, RPT-0159, RPT-0356, RPT-0511, RPT-0514, RPT-0667, RPT-0668.
    """
    candidate_names = [
        "Terminate cables in CT-101",
        "Terminate cables in CT-102",
        "Terminate cables in CT-201",
        "Terminate cables in CT-301",
    ]
    for name in candidate_names:
        result = score_activity(
            ActivityType.TERMINATE_CABLE,
            name,
            DEFAULT_ACTIVITY_SYNONYMS,
            fuzzy_match_floor=40,
        )
        assert result.score == 1.0, (
            f"TERMINATE_CABLE should score 1.0 on candidate '{name}', got {result.score}"
        )


def test_existing_terminate_cable_synonyms_still_work():
    """Existing TERMINATE_CABLE synonyms ('cable termination', 'cables terminated', etc.) must still work."""
    assert "terminate cables" in DEFAULT_ACTIVITY_SYNONYMS["TERMINATE_CABLE"]
    assert "terminate cable" in DEFAULT_ACTIVITY_SYNONYMS["TERMINATE_CABLE"]
    assert "cable termination" in DEFAULT_ACTIVITY_SYNONYMS["TERMINATE_CABLE"]
    assert "cables terminated" in DEFAULT_ACTIVITY_SYNONYMS["TERMINATE_CABLE"]

    # Test candidate names with singular and other forms
    singular_result = score_activity(
        ActivityType.TERMINATE_CABLE,
        "Terminate cable in CT-101",
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert singular_result.score == 1.0


def test_terminate_cable_does_not_match_unrelated_activities():
    """TERMINATE_CABLE type must NOT match unrelated candidate names like PULL_CABLE."""
    pull_cable_candidate = "Pull cables through CT-101"
    result = score_activity(
        ActivityType.TERMINATE_CABLE,
        pull_cable_candidate,
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.score < 0.999, (
        f"TERMINATE_CABLE should NOT score 1.0 on PULL_CABLE candidate '{pull_cable_candidate}', got {result.score}"
    )


# ---------------------------------------------------------------------------
# Regression: FIT_UP joint preparation / joint prep fix (2026-09-09)
# ---------------------------------------------------------------------------


def test_joint_preparation_matches_fit_up_activity():
    """'joint preparation' and 'joint prep' phrases must score 1.0 for FIT_UP."""
    candidate = "Perform fit-up for piping spool SP-302"
    for phrase in ["joint preparation", "joint prep"]:
        assert phrase in DEFAULT_ACTIVITY_SYNONYMS["FIT_UP"]

    result = score_activity(
        ActivityType.FIT_UP,
        candidate,
        DEFAULT_ACTIVITY_SYNONYMS,
        fuzzy_match_floor=40,
    )
    assert result.score == 1.0, f"FIT_UP on '{candidate}' should be 1.0, got {result.score}"


def test_joint_preparation_does_not_false_match_other_activities():
    """'joint preparation' must NOT match unrelated candidates like WELD or INSTALL."""
    unrelated_candidates = [
        "Weld piping spool SP-302",
        "Install piping spool SP-302",
        "Hydrotest piping spool SP-302",
    ]
    for cand in unrelated_candidates:
        res = score_activity(
            ActivityType.FIT_UP,
            cand,
            DEFAULT_ACTIVITY_SYNONYMS,
            fuzzy_match_floor=40,
        )
        assert res.score < 0.999, f"FIT_UP under '{cand}' should NOT score 1.0, got {res.score}"


