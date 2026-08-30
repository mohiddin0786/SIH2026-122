"""
module_4_matching/config.py — Externalized, tunable configuration for Module 4.

Nothing here is a business-logic decision by itself; it is the set of knobs
scorer.py / ranker.py read from. Per the integration contract, thresholds,
weights, top_k-like values, and alias/penalty tables must be configurable
rather than hardcoded inside matching logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Weighting
# ---------------------------------------------------------------------------


@dataclass
class MatchingWeights:
    """Weights for the five scoring signals. Must sum to 1.0 (validated).

    These are *initial defaults*, not claimed-optimal values — the module
    prompt explicitly says not to assume they are tuned. Override via
    MatchingConfig(weights=MatchingWeights(...)) or load_config_from_dict().
    """

    # NOTE: Tuned via tune_weights.py (2026-08-30). Zero-error combo found:
    # Eq=0.40 (strongest signal for same-tag disambiguation),
    # Date=0.15 (plausibility tie-breaker for same-tag ties),
    # Sem reduced to 0.10 (embedding similarity fails for same-tag variants).
    semantic_weight: float = 0.20   # was 0.30
    equipment_weight: float = 0.30
    activity_weight: float = 0.20
    location_weight: float = 0.15
    discipline_weight: float = 0.05
    date_weight: float = 0.10       # was 0.0

    def validate(self, tolerance: float = 1e-6) -> None:
        total = (
            self.semantic_weight
            + self.equipment_weight
            + self.activity_weight
            + self.location_weight
            + self.discipline_weight
            + self.date_weight
        )
        if any(
            w < 0.0
            for w in (
                self.semantic_weight,
                self.equipment_weight,
                self.activity_weight,
                self.location_weight,
                self.discipline_weight,
                self.date_weight,
            )
        ):
            raise ValueError("MatchingWeights: individual weights must be >= 0.0")
        if abs(total - 1.0) > tolerance:
            raise ValueError(
                f"MatchingWeights must sum to 1.0 (got {total:.6f}). "
                "Adjust semantic/equipment/activity/location/discipline/date weights."
            )

    def as_dict(self) -> Dict[str, float]:
        return {
            "semantic_score": self.semantic_weight,
            "equipment_score": self.equipment_weight,
            "activity_score": self.activity_weight,
            "location_score": self.location_weight,
            "discipline_score": self.discipline_weight,
            "date_score": self.date_weight,
        }


# ---------------------------------------------------------------------------
# Default activity-type -> text-synonym table (module 2's ActivityType enum
# values, mapped to words we'd expect to see in a schedule activity_name).
# Configurable / overridable — not meant to be exhaustive out of the box.
DEFAULT_ACTIVITY_SYNONYMS: Dict[str, List[str]] = {
    "INSTALL": ["install", "installation", "erect", "erection", "mount", "fit"],
    "WELD": ["weld", "welding"],
    "FIT_UP": ["fit-up", "fit up", "fitup", "fit"],
    "INSPECT": ["inspect", "inspection"],
    "HYDROTEST": ["hydrotest", "hydro test", "pressure test", "hydrostatic test"],
    "EXCAVATE": ["excavate", "excavation", "dig"],
    "CAST": ["cast", "casting", "pour", "concrete pour"],
    "CURE": ["cure", "curing"],
    "ALIGN": ["align", "alignment"],
    "CALIBRATE": ["calibrate", "calibration"],
    "LOOP_CHECK": ["loop check", "loop test"],
    "PULL_CABLE": ["pull cable", "cable pulling", "cabling"],
    "TERMINATE_CABLE": ["terminate cable", "cable termination", "termination"],
    "CONNECT_MOTOR": ["connect motor", "motor connection", "motor hookup"],
}

DEFAULT_DISCIPLINE_MAP: Dict[str, str] = {
    "WELD": "Piping",
    "FIT_UP": "Piping",
    "HYDROTEST": "Piping",
    "PULL_CABLE": "Electrical",
    "TERMINATE_CABLE": "Electrical",
    "CONNECT_MOTOR": "Electrical",
    "LOOP_CHECK": "Instrumentation",
    "CALIBRATE": "Instrumentation",
    "EXCAVATE": "Civil",
    "CAST": "Civil",
    "CURE": "Civil",
    "ALIGN": "Mechanical",
}


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


@dataclass
class MatchingConfig:
    weights: MatchingWeights = field(default_factory=MatchingWeights)

    # Fuzzy-matching floor (rapidfuzz, 0-100). Used for activity synonyms
    # and location typo tolerance. Equipment tags ignore this and match
    # exactly after normalize — they are identity keys, not free text.
    fuzzy_match_floor: int = 40

    # How much each individual contradiction signal (equipment mismatch,
    # location mismatch) subtracts from the combined score, via
    # final_score *= (1 - contradiction_penalty). Additive across signals,
    # capped at max_contradiction_penalty.
    contradiction_penalty_per_signal: float = 0.35
    max_contradiction_penalty: float = 0.9

    activity_synonyms: Dict[str, List[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_ACTIVITY_SYNONYMS.items()}
    )
    discipline_map: Dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_DISCIPLINE_MAP)
    )

    def __post_init__(self) -> None:
        self.weights.validate()
        if not (0 <= self.fuzzy_match_floor <= 100):
            raise ValueError("fuzzy_match_floor must be within 0-100")
        if not (0.0 <= self.contradiction_penalty_per_signal <= 1.0):
            raise ValueError("contradiction_penalty_per_signal must be within 0.0-1.0")
        if not (0.0 <= self.max_contradiction_penalty <= 1.0):
            raise ValueError("max_contradiction_penalty must be within 0.0-1.0")


def load_config_from_dict(data: Dict) -> MatchingConfig:
    """Build a MatchingConfig from a plain dict (e.g. loaded from JSON/YAML).
    Unknown keys are ignored rather than raising, so config files can be
    extended without breaking older code."""
    weights_data = data.get("weights", {})
    weights = MatchingWeights(
        semantic_weight=weights_data.get("semantic_weight", MatchingWeights.semantic_weight),
        equipment_weight=weights_data.get("equipment_weight", MatchingWeights.equipment_weight),
        activity_weight=weights_data.get("activity_weight", MatchingWeights.activity_weight),
        location_weight=weights_data.get("location_weight", MatchingWeights.location_weight),
        discipline_weight=weights_data.get("discipline_weight", MatchingWeights.discipline_weight),
        date_weight=weights_data.get("date_weight", MatchingWeights.date_weight),
    )
    kwargs = {}
    if "fuzzy_match_floor" in data:
        kwargs["fuzzy_match_floor"] = data["fuzzy_match_floor"]
    if "contradiction_penalty_per_signal" in data:
        kwargs["contradiction_penalty_per_signal"] = data["contradiction_penalty_per_signal"]
    if "max_contradiction_penalty" in data:
        kwargs["max_contradiction_penalty"] = data["max_contradiction_penalty"]
    if "activity_synonyms" in data:
        kwargs["activity_synonyms"] = data["activity_synonyms"]
    if "discipline_map" in data:
        kwargs["discipline_map"] = data["discipline_map"]
    return MatchingConfig(weights=weights, **kwargs)