"""Competition domain value objects."""

from .competition_golf_course_id import CompetitionGolfCourseId
from .competition_name import CompetitionName, InvalidCompetitionNameError
from .date_range import DateRange, InvalidDateRangeError
from .handicap_mode import HandicapMode
from .handicap_settings import (
    HandicapSettings,
    HandicapType,
    InvalidHandicapSettingsError,
)
from .location import InvalidLocationError, Location
from .match_format import MatchFormat
from .match_id import MatchId
from .match_player import MatchPlayer
from .match_status import MatchStatus
from .play_mode import PlayMode
from .round_id import RoundId
from .round_status import RoundStatus
from .schedule_config_mode import ScheduleConfigMode
from .session_type import SessionType
from .team_assignment_id import TeamAssignmentId
from .team_assignment_mode import TeamAssignmentMode

__all__ = [
    "CompetitionGolfCourseId",
    "CompetitionName",
    "DateRange",
    "HandicapMode",
    "HandicapSettings",
    "HandicapType",
    "InvalidCompetitionNameError",
    "InvalidDateRangeError",
    "InvalidHandicapSettingsError",
    "InvalidLocationError",
    "Location",
    "MatchFormat",
    "MatchId",
    "MatchPlayer",
    "MatchStatus",
    "PlayMode",
    "RoundId",
    "RoundStatus",
    "ScheduleConfigMode",
    "SessionType",
    "TeamAssignmentId",
    "TeamAssignmentMode",
]
