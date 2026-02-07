"""Tests para GetMatchDetailUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    GetMatchDetailRequestDTO,
)
from src.modules.competition.application.use_cases.get_match_detail_use_case import (
    GetMatchDetailUseCase,
    MatchNotFoundError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio


class TestGetMatchDetailUseCase:
    """Suite de tests para el caso de uso GetMatchDetailUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    @pytest.fixture
    async def competition(self, uow, creator_id):
        """Fixture que crea y persiste una competicion de prueba."""
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName("Test Competition"),
            dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.SCRATCH,
            max_players=24,
            team_assignment=TeamAssignment.MANUAL,
            team_1_name="Team A",
            team_2_name="Team B",
        )
        async with uow:
            await uow.competitions.add(competition)
        return competition

    @pytest.fixture
    async def round_entity(self, uow, competition):
        """Fixture que crea y persiste una ronda de prueba."""
        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with uow:
            await uow.rounds.add(round_entity)
        return round_entity

    async def test_should_return_match_detail(
        self, uow: InMemoryUnitOfWork, round_entity
    ):
        """
        Verifica que se retorna el detalle completo de un partido.

        Given: Una ronda con un partido con jugadores
        When: Se solicita el detalle del partido
        Then: Se retornan todos los campos incluyendo jugadores y contexto de ronda
        """
        # Arrange
        user_a_id = UserId(uuid4())
        user_b_id = UserId(uuid4())
        player_a = MatchPlayer.create(
            user_id=user_a_id,
            playing_handicap=12,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6],
            tee_gender=Gender.MALE,
        )
        player_b = MatchPlayer.create(
            user_id=user_b_id,
            playing_handicap=8,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[1, 3, 5, 7, 9, 11, 13, 15],
            tee_gender=Gender.FEMALE,
        )
        match = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )
        async with uow:
            await uow.matches.add(match)

        # Act
        use_case = GetMatchDetailUseCase(uow=uow)
        request = GetMatchDetailRequestDTO(match_id=str(match.id.value))
        response = await use_case.execute(request)

        # Assert: campos del partido
        assert response.id == match.id.value
        assert response.round_id == round_entity.id.value
        assert response.match_number == 1
        assert response.status == "SCHEDULED"

        # Assert: jugadores equipo A
        assert len(response.team_a_players) == 1
        assert response.team_a_players[0].user_id == user_a_id.value
        assert response.team_a_players[0].playing_handicap == 12
        assert response.team_a_players[0].tee_category == "AMATEUR"
        assert response.team_a_players[0].strokes_received == [1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6]

        # Assert: jugadores equipo B
        assert len(response.team_b_players) == 1
        assert response.team_b_players[0].user_id == user_b_id.value
        assert response.team_b_players[0].playing_handicap == 8
        assert response.team_b_players[0].tee_category == "AMATEUR"
        assert response.team_b_players[0].strokes_received == [1, 3, 5, 7, 9, 11, 13, 15]

        # Assert: contexto de ronda
        assert response.round_date == date(2026, 6, 1)
        assert response.session_type == "MORNING"
        assert response.match_format == "SINGLES"

        # Assert: handicap strokes
        assert response.handicap_strokes_given >= 0
        assert response.result is None

    async def test_should_fail_when_match_not_found(
        self, uow: InMemoryUnitOfWork
    ):
        """
        Verifica que se lanza error cuando el partido no existe.

        Given: Un ID de partido inexistente
        When: Se solicita el detalle
        Then: Se lanza MatchNotFoundError
        """
        # Arrange
        fake_id = uuid4()

        # Act & Assert
        use_case = GetMatchDetailUseCase(uow=uow)
        request = GetMatchDetailRequestDTO(match_id=str(fake_id))
        with pytest.raises(MatchNotFoundError) as exc_info:
            await use_case.execute(request)

        assert str(fake_id) in str(exc_info.value)

    async def test_should_include_round_context(
        self, uow: InMemoryUnitOfWork, competition
    ):
        """
        Verifica que el detalle del partido incluye informacion de la ronda.

        Given: Una ronda AFTERNOON con formato FOURBALL y un partido
        When: Se solicita el detalle del partido
        Then: La respuesta incluye round_date, session_type y match_format de la ronda
        """
        # Arrange: Crear ronda con session_type y match_format especificos
        round_afternoon = Round.create(
            competition_id=competition.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 2),
            session_type=SessionType.AFTERNOON,
            match_format=MatchFormat.FOURBALL,
        )
        async with uow:
            await uow.rounds.add(round_afternoon)

        # Crear partido fourball (2v2)
        player_a1 = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=10,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        player_a2 = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=15,
            tee_category=TeeCategory.SENIOR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        player_b1 = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=8,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        player_b2 = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=12,
            tee_category=TeeCategory.SENIOR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        match = Match.create(
            round_id=round_afternoon.id,
            match_number=1,
            team_a_players=[player_a1, player_a2],
            team_b_players=[player_b1, player_b2],
        )
        async with uow:
            await uow.matches.add(match)

        # Act
        use_case = GetMatchDetailUseCase(uow=uow)
        request = GetMatchDetailRequestDTO(match_id=str(match.id.value))
        response = await use_case.execute(request)

        # Assert: contexto de la ronda
        assert response.round_date == date(2026, 6, 2)
        assert response.session_type == "AFTERNOON"
        assert response.match_format == "FOURBALL"

        # Assert: verificar que es fourball (2v2)
        assert len(response.team_a_players) == 2
        assert len(response.team_b_players) == 2
