"""Tests para GetScheduleUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    GetScheduleRequestDTO,
)
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    CompetitionNotFoundError,
    GetScheduleUseCase,
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

pytestmark = pytest.mark.asyncio


class TestGetScheduleUseCase:
    """Suite de tests para el caso de uso GetScheduleUseCase."""

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

    async def test_should_return_schedule_with_rounds_and_matches(
        self, uow: InMemoryUnitOfWork, competition
    ):
        """
        Verifica que se retorna el schedule con rondas y partidos correctamente.

        Given: Una competicion con 2 rondas (morning y afternoon) y partidos en cada una
        When: Se solicita el schedule
        Then: Se retorna el schedule agrupado por dia con total_rounds=2 y partidos
        """
        # Arrange: Crear 2 rondas en el mismo dia (morning y afternoon)
        round_1 = Round.create(
            competition_id=competition.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_2 = Round.create(
            competition_id=competition.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 1),
            session_type=SessionType.AFTERNOON,
            match_format=MatchFormat.FOURBALL,
        )
        async with uow:
            await uow.rounds.add(round_1)
            await uow.rounds.add(round_2)

        # Crear partidos para la primera ronda
        player_a = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        player_b = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        match_1 = Match.create(
            round_id=round_1.id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )
        async with uow:
            await uow.matches.add(match_1)

        # Crear partido para la segunda ronda (fourball: 2v2)
        player_c = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=5,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        player_d = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=3,
            tee_category=TeeCategory.AMATEUR_FEMALE,
            strokes_received=[],
        )
        player_e = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=4,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        player_f = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=2,
            tee_category=TeeCategory.AMATEUR_FEMALE,
            strokes_received=[],
        )
        match_2 = Match.create(
            round_id=round_2.id,
            match_number=1,
            team_a_players=[player_c, player_d],
            team_b_players=[player_e, player_f],
        )
        async with uow:
            await uow.matches.add(match_2)

        # Act
        use_case = GetScheduleUseCase(uow=uow)
        request = GetScheduleRequestDTO(competition_id=str(competition.id.value))
        response = await use_case.execute(request)

        # Assert
        assert response.competition_id == competition.id.value
        assert response.total_rounds == 2
        assert response.total_matches == 2
        assert len(response.days) == 1  # Ambas rondas en el mismo dia
        assert response.days[0].day_date == date(2026, 6, 1)
        assert len(response.days[0].rounds) == 2

        # Verificar que las rondas estan ordenadas por session_type (alphabetical)
        round_dtos = response.days[0].rounds
        assert round_dtos[0].session_type == "AFTERNOON"
        assert round_dtos[1].session_type == "MORNING"

        # Verificar partidos en cada ronda
        assert len(round_dtos[0].matches) == 1
        assert len(round_dtos[1].matches) == 1

    async def test_should_return_empty_schedule(
        self, uow: InMemoryUnitOfWork, competition
    ):
        """
        Verifica que se retorna un schedule vacio cuando no hay rondas.

        Given: Una competicion sin rondas
        When: Se solicita el schedule
        Then: Se retorna days vacio, total_rounds=0, total_matches=0
        """
        # Act
        use_case = GetScheduleUseCase(uow=uow)
        request = GetScheduleRequestDTO(competition_id=str(competition.id.value))
        response = await use_case.execute(request)

        # Assert
        assert response.competition_id == competition.id.value
        assert response.days == []
        assert response.total_rounds == 0
        assert response.total_matches == 0
        assert response.team_assignment is None

    async def test_should_fail_when_competition_not_found(
        self, uow: InMemoryUnitOfWork
    ):
        """
        Verifica que se lanza error cuando la competicion no existe.

        Given: Un ID de competicion inexistente
        When: Se solicita el schedule
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        fake_id = uuid4()

        # Act & Assert
        use_case = GetScheduleUseCase(uow=uow)
        request = GetScheduleRequestDTO(competition_id=str(fake_id))
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await use_case.execute(request)

        assert str(fake_id) in str(exc_info.value)

    async def test_should_return_multi_day_schedule(
        self, uow: InMemoryUnitOfWork, competition
    ):
        """
        Verifica que rondas en dias distintos se agrupan correctamente.

        Given: Rondas en date(2026,6,1) y date(2026,6,2)
        When: Se solicita el schedule
        Then: Se retornan 2 dias ordenados por fecha
        """
        # Arrange: Crear rondas en dos dias distintos
        round_day1 = Round.create(
            competition_id=competition.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_day2 = Round.create(
            competition_id=competition.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 2),
            session_type=SessionType.AFTERNOON,
            match_format=MatchFormat.FOURSOMES,
        )
        async with uow:
            await uow.rounds.add(round_day1)
            await uow.rounds.add(round_day2)

        # Crear un partido en cada ronda
        player_a = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        player_b = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        match_day1 = Match.create(
            round_id=round_day1.id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )

        player_c = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=10,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        player_d = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=8,
            tee_category=TeeCategory.AMATEUR_FEMALE,
            strokes_received=[],
        )
        player_e = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=6,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        player_f = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=4,
            tee_category=TeeCategory.AMATEUR_FEMALE,
            strokes_received=[],
        )
        match_day2 = Match.create(
            round_id=round_day2.id,
            match_number=1,
            team_a_players=[player_c, player_d],
            team_b_players=[player_e, player_f],
        )
        async with uow:
            await uow.matches.add(match_day1)
            await uow.matches.add(match_day2)

        # Act
        use_case = GetScheduleUseCase(uow=uow)
        request = GetScheduleRequestDTO(competition_id=str(competition.id.value))
        response = await use_case.execute(request)

        # Assert: 2 dias ordenados por fecha
        assert len(response.days) == 2
        assert response.days[0].day_date == date(2026, 6, 1)
        assert response.days[1].day_date == date(2026, 6, 2)
        assert response.total_rounds == 2
        assert response.total_matches == 2

        # Verificar que cada dia tiene su ronda correspondiente
        assert len(response.days[0].rounds) == 1
        assert response.days[0].rounds[0].session_type == "MORNING"
        assert response.days[0].rounds[0].match_format == "SINGLES"

        assert len(response.days[1].rounds) == 1
        assert response.days[1].rounds[0].session_type == "AFTERNOON"
        assert response.days[1].rounds[0].match_format == "FOURSOMES"
