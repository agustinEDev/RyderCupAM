"""
Tests de GetLeaderboardUseCase, centrados en cómo se resuelve el nombre de
cada jugador.

La clasificación pinta `display_name` (BE #239) salvo que la inscripción de
esa persona en ESTA competición haya elegido su nombre legal (BE #254). No
existía ningún test de este caso de uso antes de esta issue.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def user_repo():
    """Un repositorio donde `display_name` NO coincide con nombre+apellido."""

    def _make(uid):
        user = MagicMock()
        user.id = uid
        user.first_name = "Nombre"
        user.last_name = "Legal"
        user.display_name = "Chuchi"
        user.get_full_name = MagicMock(return_value="Nombre Legal")
        return user

    repo = AsyncMock()
    repo.find_by_ids = AsyncMock(side_effect=lambda uids: [_make(u) for u in uids])
    return repo


async def _setup_scheduled_match(uow: InMemoryUnitOfWork):
    """
    Una competición con una ronda y un partido SCHEDULED entre dos jugadores.

    SCHEDULED no está terminado ni admite anotación (`can_record_scores()` es
    False), así que el caso de uso no entra en ninguna de las dos ramas de
    cálculo de resultado: lo único que se ejercita es la resolución del
    nombre de cada jugador, que es lo único que prueba este fichero.
    """
    player_a = MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=10,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=[],
    )
    player_b = MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=18,
        tee_color=TeeColor.RED,
        tee_gender=Gender.FEMALE,
        strokes_received=[],
    )

    round_id = RoundId.generate()
    competition_id = CompetitionId.generate()

    mock_round = MagicMock()
    mock_round.id = round_id
    mock_round.competition_id = competition_id
    mock_round.match_format = MagicMock(value="SINGLES")

    match = Match.create(
        round_id=round_id, match_number=1, team_a_players=[player_a], team_b_players=[player_b]
    )
    await uow.matches.add(match)
    uow._rounds._rounds[round_id] = mock_round

    mock_comp = MagicMock()
    mock_comp.id = competition_id
    mock_comp.name = "Test Cup"
    mock_comp.team_1_name = "Team A"
    mock_comp.team_2_name = "Team B"
    uow._competitions._competitions[competition_id] = mock_comp

    return competition_id, player_a, player_b


class TestLeaderboardPaintsTheDisplayName:
    """La clasificación pinta `display_name` por defecto (BE #239)."""

    @pytest.mark.asyncio
    async def test_players_are_named_by_their_display_name(self, uow, user_repo):
        competition_id, player_a, _player_b = await _setup_scheduled_match(uow)
        uc = GetLeaderboardUseCase(uow, user_repo, ScoringService())

        view = await uc.execute(str(competition_id))

        names = {p.user_id for m in view.matches for p in (*m.team_a_players, *m.team_b_players)}
        user_names = {
            p.user_name for m in view.matches for p in (*m.team_a_players, *m.team_b_players)
        }
        assert str(player_a.user_id) in names
        assert user_names == {"Chuchi"}


class TestLeaderboardRespectsNamePreference:
    """
    Salvo que la inscripción de esa competición haya elegido el nombre legal
    (BE #254), en cuyo caso ese jugador se pinta por su nombre y el resto
    sigue por su alias.
    """

    @pytest.mark.asyncio
    async def test_el_jugador_que_eligio_su_nombre_legal_se_pinta_por_el(self, uow, user_repo):
        competition_id, player_a, player_b = await _setup_scheduled_match(uow)
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=competition_id,
            user_id=player_a.user_id,
        )
        enrollment.set_name_preference(True)
        await uow.enrollments.add(enrollment)

        uc = GetLeaderboardUseCase(uow, user_repo, ScoringService())
        view = await uc.execute(str(competition_id))

        user_names = {
            p.user_id: p.user_name
            for m in view.matches
            for p in (*m.team_a_players, *m.team_b_players)
        }
        assert user_names[str(player_a.user_id)] == "Nombre Legal"
        assert user_names[str(player_b.user_id)] == "Chuchi"
