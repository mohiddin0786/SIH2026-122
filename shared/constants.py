"""
shared/constants.py — Fixed, allowed values (Enums) for the pipeline.

RULE: Fixed values must come only from here. Modules must not invent
alternative spellings (e.g. "COMPLETED" instead of "FINISH").
"""

from enum import Enum


class EventType(str, Enum):
    """What kind of execution event a report describes."""
    START = "START"
    PROGRESS = "PROGRESS"
    FINISH = "FINISH"
    UNKNOWN = "UNKNOWN"


class DecisionType(str, Enum):
    """The three allowed outcomes of Module 5 (Confidence & Decision)."""
    AUTO_MATCH = "AUTO_MATCH"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    UNMATCHED = "UNMATCHED"


class ExecutionStatus(str, Enum):
    """Actual, as-built execution status of a schedule activity."""
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"


class UpdateStatus(str, Enum):
    """Result of Module 6's attempt to update execution state."""
    UPDATED = "UPDATED"
    PENDING_REVIEW = "PENDING_REVIEW"
    NO_UPDATE = "NO_UPDATE"


class ActivityType(str, Enum):
    """Controlled vocabulary for the kind of work a report describes."""
    INSTALL = "INSTALL"
    WELD = "WELD"
    FIT_UP = "FIT_UP"
    INSPECT = "INSPECT"
    HYDROTEST = "HYDROTEST"
    EXCAVATE = "EXCAVATE"
    CAST = "CAST"
    CURE = "CURE"
    ALIGN = "ALIGN"
    CALIBRATE = "CALIBRATE"
    LOOP_CHECK = "LOOP_CHECK"
    PULL_CABLE = "PULL_CABLE"
    TERMINATE_CABLE = "TERMINATE_CABLE"
    CONNECT_MOTOR = "CONNECT_MOTOR"
    UNKNOWN = "UNKNOWN"


class LabelType(str, Enum):
    """Ground-truth label categories (Module 7 / evaluation only)."""
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"