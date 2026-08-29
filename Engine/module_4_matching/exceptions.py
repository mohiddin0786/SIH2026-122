"""Re-export the shared MatchingError so Module 4 does not fork the contract."""

from shared.exceptions import MatchingError

__all__ = ["MatchingError"]
