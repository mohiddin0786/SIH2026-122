"""module_4_matching — Detailed matching & ranking (Module 4 of the pipeline)."""

from shared.exceptions import MatchingError

from .config import MatchingConfig, MatchingWeights, load_config_from_dict
from .ranker import rank_candidates

__all__ = [
    "rank_candidates",
    "MatchingConfig",
    "MatchingWeights",
    "load_config_from_dict",
    "MatchingError",
]