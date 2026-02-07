"""Helper factories para tests de infraestructura de Competition."""

from datetime import date

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


def create_round(
    competition_id: CompetitionId | None = None,
    golf_course_id: GolfCourseId | None = None,
    round_date: date | None = None,
    session_type: SessionType = SessionType.MORNING,
    match_format: MatchFormat = MatchFormat.SINGLES,
) -> Round:
    """Crea un Round con valores por defecto para testing."""
    return Round.create(
        competition_id=competition_id or CompetitionId.generate(),
        golf_course_id=golf_course_id or GolfCourseId.generate(),
        round_date=round_date or date(2026, 3, 15),
        session_type=session_type,
        match_format=match_format,
    )


def create_match(
    round_id: RoundId | None = None,
    match_number: int = 1,
) -> Match:
    """Crea un Match con jugadores por defecto para testing."""
    player_a = MatchPlayer(
        user_id=UserId.generate(),
        playing_handicap=12,
        tee_category=TeeCategory.AMATEUR,
        tee_gender=Gender.MALE,
        strokes_received=(1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6),
    )
    player_b = MatchPlayer(
        user_id=UserId.generate(),
        playing_handicap=8,
        tee_category=TeeCategory.AMATEUR,
        tee_gender=Gender.MALE,
        strokes_received=(1, 3, 5, 7, 9, 11, 13, 15),
    )
    return Match.create(
        round_id=round_id or RoundId.generate(),
        match_number=match_number,
        team_a_players=[player_a],
        team_b_players=[player_b],
    )


def create_team_assignment(
    competition_id: CompetitionId | None = None,
    mode: TeamAssignmentMode = TeamAssignmentMode.MANUAL,
) -> TeamAssignment:
    """Crea un TeamAssignment con jugadores por defecto para testing."""
    return TeamAssignment.create(
        competition_id=competition_id or CompetitionId.generate(),
        mode=mode,
        team_a_player_ids=[UserId.generate(), UserId.generate()],
        team_b_player_ids=[UserId.generate(), UserId.generate()],
    )
