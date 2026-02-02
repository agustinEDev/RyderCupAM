"""Competition domain value objects."""

from .competition_golf_course_id import CompetitionGolfCourseId
from .competition_name import CompetitionName, InvalidCompetitionNameError
from .date_range import DateRange, InvalidDateRangeError
from .handicap_settings import (
    HandicapSettings,
    HandicapType,
    InvalidHandicapSettingsError,
)
from .location import InvalidLocationError, Location

__all__ = [
    "CompetitionGolfCourseId",
    "CompetitionName",
    "DateRange",
    "HandicapSettings",
    "HandicapType",
    "InvalidCompetitionNameError",
    "InvalidDateRangeError",
    "InvalidHandicapSettingsError",
    "InvalidLocationError",
    "Location",
]
