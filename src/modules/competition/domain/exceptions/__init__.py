"""Competition Domain Exceptions."""

from .competition_violations import (
    CompetitionFullViolation,
    DuplicateEnrollmentViolation,
    EnrollmentPastStartDateViolation,
    InvalidCompetitionStatusViolation,
    InvalidDateRangeViolation,
    MaxCompetitionsExceededViolation,
    MaxDurationExceededViolation,
    MaxEnrollmentsExceededViolation,
)

__all__ = [
    "CompetitionFullViolation",
    "DuplicateEnrollmentViolation",
    "EnrollmentPastStartDateViolation",
    "InvalidCompetitionStatusViolation",
    "InvalidDateRangeViolation",
    "MaxCompetitionsExceededViolation",
    "MaxDurationExceededViolation",
    "MaxEnrollmentsExceededViolation",
]
