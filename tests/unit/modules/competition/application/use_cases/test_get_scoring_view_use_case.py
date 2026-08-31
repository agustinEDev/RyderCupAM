"""
Tests de GetScoringViewUseCase, centrados en la tarjeta de cada jugador.

El par, el índice y los metros son de la barra desde la que se juega, no del
campo: `reference_card` es solo la tarjeta derivada de la primera salida con
tarjeta, y de los 800 campos federados con más de una, 56 cambian de stroke
index entre ellas y 25 de par. Servir esa tarjeta a todo el partido le enseña a
quien no juega la primera barra un par que no es el suyo, mientras sus golpes
sí se reparten con el índice de la suya.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.use_cases.get_scoring_view_use_case import (
    GetScoringViewUseCase,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

PAR_72 = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]


def _card(pars: list[int], meters: int) -> list[Hole]:
    return [
        Hole(number=i + 1, par=pars[i], stroke_index=i + 1, meters=meters) for i in range(18)
    ]


def _course_two_tees() -> GolfCourse:
    """
    Amarillas y rojas con tarjetas distintas.

    El hoyo 1 juega par 4 desde amarillas y par 5 desde rojas: es el caso real
    del hoyo que las mujeres juegan como par 5 y los hombres como par 4.
    """
    red_pars = list(PAR_72)
    red_pars[0] = 5
    return GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                course_rating=71.0,
                slope_rating=128,
                holes=_card(PAR_72, meters=350),
            ),
            Tee(
                color=TeeColor.RED,
                gender=Gender.FEMALE,
                course_rating=73.0,
                slope_rating=131,
                holes=_card(red_pars, meters=300),
            ),
        ],
        holes=_card(PAR_72, meters=350),
    )


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def user_repo():
    def _make_mock_user(uid):
        user = MagicMock()
        user.first_name = "Player"
        user.last_name = str(uid)[:8]
        # La vista de anotación pinta `display_name` (BE #239): sin esto el
        # mock devuelve otro MagicMock y el DTO lo rechaza por no ser texto
        user.display_name = f"Player {str(uid)[:8]}"
        return user

    repo = AsyncMock()
    repo.find_by_id = AsyncMock(side_effect=_make_mock_user)
    return repo


async def _setup(uow, course: GolfCourse | None):
    """Un partido de dos jugadores, uno por barra, listo para pedir la vista."""
    yellow = MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=10,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=[],
    )
    red = MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=18,
        tee_color=TeeColor.RED,
        tee_gender=Gender.FEMALE,
        strokes_received=[],
    )
    round_id = RoundId.generate()
    mock_round = MagicMock()
    mock_round.id = round_id
    mock_round.competition_id = MagicMock()
    mock_round.round_date = None
    mock_round.session_type = MagicMock(value="MORNING")
    mock_round.match_format = MagicMock(value="SINGLES")
    mock_round.golf_course_id = MagicMock()

    match = Match.create(
        round_id=round_id, match_number=1, team_a_players=[yellow], team_b_players=[red]
    )
    match.start()
    await uow.matches.add(match)
    uow._rounds._rounds[round_id] = mock_round

    mock_comp = MagicMock()
    mock_comp.id = mock_round.competition_id
    mock_comp.team_1_name = "Team A"
    mock_comp.team_2_name = "Team B"
    uow._competitions._competitions[mock_comp.id] = mock_comp

    gc_repo = AsyncMock()
    gc_repo.find_by_id = AsyncMock(return_value=course)
    return match, yellow, red, gc_repo


class TestHoleCardPerPlayer:
    @pytest.mark.asyncio
    async def test_cada_jugador_recibe_la_tarjeta_de_su_barra(self, uow, user_repo):
        match, yellow, red, gc_repo = await _setup(uow, _course_two_tees())
        uc = GetScoringViewUseCase(uow, user_repo, ScoringService(), gc_repo)

        view = await uc.execute(str(match.id))

        cards = {p.user_id: p.hole_card for p in view.players}
        assert cards[str(yellow.user_id)][0].par == 4
        assert cards[str(red.user_id)][0].par == 5

    @pytest.mark.asyncio
    async def test_la_tarjeta_lleva_los_metros_de_su_barra(self, uow, user_repo):
        match, yellow, red, gc_repo = await _setup(uow, _course_two_tees())
        uc = GetScoringViewUseCase(uow, user_repo, ScoringService(), gc_repo)

        view = await uc.execute(str(match.id))

        cards = {p.user_id: p.hole_card for p in view.players}
        assert cards[str(yellow.user_id)][0].meters == 350
        assert cards[str(red.user_id)][0].meters == 300

    @pytest.mark.asyncio
    async def test_la_tarjeta_viene_ordenada_y_completa(self, uow, user_repo):
        match, yellow, _, gc_repo = await _setup(uow, _course_two_tees())
        uc = GetScoringViewUseCase(uow, user_repo, ScoringService(), gc_repo)

        view = await uc.execute(str(match.id))

        card = next(p.hole_card for p in view.players if p.user_id == str(yellow.user_id))
        assert [hole.hole_number for hole in card] == list(range(1, 19))

    @pytest.mark.asyncio
    async def test_sin_campo_cargado_los_jugadores_van_sin_tarjeta(self, uow, user_repo):
        """
        La vista ya sale sin hoyos cuando no hay campo; lo que no puede es
        reventar ni inventarse una tarjeta.
        """
        match, _, _, gc_repo = await _setup(uow, None)
        uc = GetScoringViewUseCase(uow, user_repo, ScoringService(), gc_repo)

        view = await uc.execute(str(match.id))

        assert view.holes == []
        assert all(p.hole_card == [] for p in view.players)


class TestScoringViewPaintsTheDisplayName:
    """
    La vista de anotación pinta `display_name`, no el nombre legal (BE #239).

    Es la pantalla donde más se lee un nombre —quién anota a quién—, y el
    campo ya era «nombre para enseñar», así que lo único que cambia es de
    dónde sale.
    """

    @pytest.fixture
    def user_repo_con_alias(self):
        """Un repositorio donde `display_name` NO coincide con nombre+apellido."""

        def _make(uid):
            user = MagicMock()
            user.first_name = "Nombre"
            user.last_name = "Legal"
            user.display_name = "Chuchi"
            return user

        repo = AsyncMock()
        repo.find_by_id = AsyncMock(side_effect=_make)
        return repo

    @pytest.mark.asyncio
    async def test_players_are_named_by_their_display_name(self, uow, user_repo_con_alias):
        match, _yellow, _red, gc_repo = await _setup(uow, _course_two_tees())
        uc = GetScoringViewUseCase(uow, user_repo_con_alias, ScoringService(), gc_repo)

        view = await uc.execute(str(match.id))

        assert {p.user_name for p in view.players} == {"Chuchi"}
        assert "Nombre Legal" not in {p.user_name for p in view.players}
