"""Competition domain value objects."""

from .competition_name import CompetitionName, InvalidCompetitionNameError
from .date_range import DateRange, InvalidDateRangeError
from .handicap_settings import HandicapSettings, HandicapType, InvalidHandicapSettingsError
from .location import InvalidLocationError, Location

__all__ = [
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
