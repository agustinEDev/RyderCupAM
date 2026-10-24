"""
La raya pierde el hoyo en los cuatro sitios que calculan el partido de un
torneo (Agustin, 24 oct 2026): la anotacion, el partido decidido antes del 18,
el resultado al entregar la tarjeta y la clasificacion. Antes el hoyo con raya
se quedaba sin resultado y el partido lo ganaba quien recogia.
"""

from unittest.mock import MagicMock

import pytest

from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.application.use_cases.get_scoring_view_use_case import (
    GetScoringViewUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat

pytestmark = pytest.mark.asyncio


def _jugador() -> MatchPlayer:
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=10,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
    )


def _ronda(uow: InMemoryUnitOfWork, formato: MatchFormat):
    ronda = MagicMock()
    ronda.id = RoundId.generate()
    ronda.match_format = formato
    ronda.status = RoundStatus.IN_PROGRESS
    ronda.competition_id = MagicMock()
    uow._rounds._rounds[ronda.id] = ronda
    return ronda


async def _anota(uow, match, jugador, team, hoyo, golpes, *, validada=True) -> HoleScore:
    fila = HoleScore.create(
        match_id=match.id,
        hole_number=hoyo,
        player_user_id=jugador.user_id,
        team=team,
        strokes_received=0,
    )
    fila.set_own_score(golpes)
    if validada:
        fila.set_marker_score(golpes)
    fila.recalculate_validation()
    await uow.hole_scores.add(fila)
    return fila


async def _a_recoge_en(uow, hoyos: int):
    """Individual: A recoge en los primeros `hoyos` y B los acaba con 5."""
    a, b = _jugador(), _jugador()
    ronda = _ronda(uow, MatchFormat.SINGLES)
    match = Match.create(round_id=ronda.id, match_number=1, team_a_players=[a], team_b_players=[b])
    match.start()
    await uow.matches.add(match)
    for hoyo in range(1, hoyos + 1):
        await _anota(uow, match, a, "A", hoyo, None)
        await _anota(uow, match, b, "B", hoyo, 5)
    return match, ronda, a, b


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


async def test_the_scoring_view_gives_the_hole_to_the_rival(uow):
    match, ronda, _, b = await _a_recoge_en(uow, 2)
    filas = await uow.hole_scores.find_by_match(match.id)

    hoyos, resultados = GetScoringViewUseCase(uow, MagicMock(), ScoringService())._build_scores(
        filas, ronda
    )

    assert resultados == ["B", "B"]
    assert [h.hole_result.winner for h in hoyos] == ["B", "B"]
    assert hoyos[-1].hole_result.standing == "2UP"
    assert hoyos[-1].hole_result.best_ball_player_b == [str(b.user_id)]


async def test_the_scoring_view_leaves_a_fourball_hole_open_until_the_four_balls(uow):
    a1, a2, b1, b2 = _jugador(), _jugador(), _jugador(), _jugador()
    ronda = _ronda(uow, MatchFormat.FOURBALL)
    match = Match.create(
        round_id=ronda.id, match_number=1, team_a_players=[a1, a2], team_b_players=[b1, b2]
    )
    await _anota(uow, match, a1, "A", 1, 4)
    await _anota(uow, match, a2, "A", 1, 5)
    await _anota(uow, match, b1, "B", 1, 5)
    await _anota(uow, match, b2, "B", 1, 3, validada=False)
    filas = await uow.hole_scores.find_by_match(match.id)

    hoyos, resultados = GetScoringViewUseCase(uow, MagicMock(), ScoringService())._build_scores(
        filas, ronda
    )

    assert resultados == []
    assert hoyos[0].hole_result is None


async def test_the_match_is_decided_early_with_rayas(uow):
    match, _, _, _ = await _a_recoge_en(uow, 10)

    await SubmitHoleScoreUseCase(uow, MagicMock(), ScoringService())._check_decided(
        match, match.id, MatchFormat.SINGLES
    )

    assert match.is_decided is True
    assert match.decided_result == {"winner": "B", "score": "10&8"}


async def test_the_scorecard_gives_the_match_to_the_rival(uow):
    match, _, _, b = await _a_recoge_en(uow, 10)

    respuesta = await SubmitScorecardUseCase(uow, ScoringService()).execute(
        str(match.id), b.user_id
    )

    assert (respuesta.result.winner, respuesta.result.score) == ("B", "10&8")
    assert (respuesta.stats.holes_won, respuesta.stats.holes_lost) == (10, 0)


async def test_the_leaderboard_counts_the_holes_with_raya(uow):
    match, ronda, _, _ = await _a_recoge_en(uow, 3)

    estado = await GetLeaderboardUseCase(
        uow, MagicMock(), ScoringService()
    )._compute_in_progress_standing(match, ronda)

    assert estado == ("3UP", "B", 3)


async def test_the_leaderboard_result_of_a_finished_match_counts_the_rayas(uow):
    match, _, _, _ = await _a_recoge_en(uow, 10)

    resultado = await GetLeaderboardUseCase(
        uow, MagicMock(), ScoringService()
    )._compute_decided_result(match, MatchFormat.SINGLES)

    assert resultado == {"winner": "B", "score": "10&8"}
