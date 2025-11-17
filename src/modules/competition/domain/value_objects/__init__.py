# -*- coding: utf-8 -*-
"""Competition domain value objects."""

from .competition_name import CompetitionName, InvalidCompetitionNameError
from .date_range import DateRange, InvalidDateRangeError
from .handicap_settings import HandicapSettings, HandicapType, InvalidHandicapSettingsError
from .location import Location, InvalidLocationError

__all__ = [
    "CompetitionName",
    "InvalidCompetitionNameError",
    "DateRange",
    "InvalidDateRangeError",
    "HandicapSettings",
    "HandicapType",
    "InvalidHandicapSettingsError",
    "Location",
    "InvalidLocationError",
]
