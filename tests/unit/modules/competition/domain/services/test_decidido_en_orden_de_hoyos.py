"""
El «N&M» de un partido de torneo, en el orden de los hoyos (Agustin, 25 oct
2026). El revisor del Kind dejo abiertos el 4 y el 5 de un fourball y cerro el
resto hasta el 17: el partido se dio por decidido con un «5&4» contado sin
orden. Ahora se decide en el primer hoyo en que la ventaja supera a los que
quedan, con todos los anteriores cerrados; si hay un hueco antes, se espera.

    #   caso                                                  | esperado
    ----|-----------------------------------------------------|---------------------------
    D1  fourball con los hoyos cerrados en orden, decidido 16 | «3&2»
    D2  el 4 y el 5 abiertos, el resto hasta el 17 (revisor)  | sigue en juego
    D3  se cierran el 4 y el 5                                | «3&2», no «5&4»
    D4  decidido en el 10 y el 12 en disputa                  | «10&8»
    D5  1UP en el 18 / empate en el 18                        | en test_match_play_scoring
    D6  individual y foursomes                                | igual
    D7  la clasificacion del torneo                           | el mismo N&M que se guarda
    R1  terminado con el 4 y el 5 sin anotar, sin decidir     | la ventaja: «5UP», no «5&3»
    R2  la entrega de la tarjeta en ese caso                  | se guarda «5UP»
    R3  igual, empatado                                       | «AS»
    R4  decidido «10&8» y el 3 pasa a estar en disputa        | deja de estar decidido
    R5  decidido «10&8» y el 3 cambia de ganador              | el resultado nuevo («9&7»)
    R6  se resuelve la disputa del R4                         | vuelve a «10&8»
    R7  con una tarjeta ya entregada                          | lo decidido no se mueve
    R8  la anotacion, decidido en el 10 y anotado mas alla    | el estado del 10: 10UP, quedan 8
    R9  la clasificacion en juego, igual                      | 10UP, hoyo 10
    R10 sin decidir                                           | como antes

La partida rapida (D8-D10), en test_match_play_reading,
test_get_quick_match_use_case y test_get_recent_matches_use_case.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
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
from src.modules.competition.domain.value_objects.marker_assignment import MarkerAssignment
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat

F = MatchFormat
GOLPES = {"A": (4, 5), "B": (5, 4), "HALVED": (4, 4)}

# Gana A el 1, 2, 3, 6 y 7; del 8 al 17, empatados. Con el 4 y el 5 para B,
# en orden queda decidido en el 16 por «3&2»
REVISOR = {
    **dict.fromkeys((1, 2, 3, 6, 7), "A"),
    **dict.fromkeys(range(8, 18), "HALVED"),
}
CERRADO = {**REVISOR, 4: "B", 5: "B"}
# Decidido en el 10; el 12, en disputa
DECIDIDO_EN_EL_10 = dict.fromkeys((*range(1, 12), 13, 14), "A")


def _jugador() -> MatchPlayer:
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
    )


def _partido(formato: MatchFormat) -> Match:
    por_bando = 1 if formato == F.SINGLES else 2
    match = Match.create(
        round_id=RoundId.generate(),
        match_number=1,
        team_a_players=[_jugador() for _ in range(por_bando)],
        team_b_players=[_jugador() for _ in range(por_bando)],
    )
    match.start()
    return match


def _filas(match: Match, resultados: dict[int, str], abiertos=()) -> list[HoleScore]:
    """
    Las filas validadas de cada hoyo. En los `abiertos`, la bola del primer
    jugador de A queda sin anotar: en fourball e individual el hoyo no se
    puede adjudicar; en foursomes, su bola esta en disputa.
    """
    filas = []
    for hoyo in sorted({*resultados, *abiertos}):
        golpes = GOLPES[resultados.get(hoyo, "HALVED")]
        for team, jugadores, golpe in (
            ("A", match.team_a_players, golpes[0]),
            ("B", match.team_b_players, golpes[1]),
        ):
            for i, jugador in enumerate(jugadores):
                fila = HoleScore.create(
                    match_id=match.id,
                    hole_number=hoyo,
                    player_user_id=jugador.user_id,
                    team=team,
                    strokes_received=0,
                )
                fila.set_own_score(golpe)
                if hoyo in abiertos and team == "A" and i == 0:
                    fila.set_marker_score(golpe + 1)
                else:
                    fila.set_marker_score(golpe)
                fila.recalculate_validation()
                filas.append(fila)
    return filas


def _decidido(formato, resultados, abiertos=()):
    match = _partido(formato)
    return ScoringService().decided_result(_filas(match, resultados, abiertos), formato)


class TestElServicioDeTorneo:
    def test_d1_fourball_closed_in_order_is_3_and_2(self):
        assert _decidido(F.FOURBALL, CERRADO) == {"winner": "A", "score": "3&2"}

    def test_d2_with_the_4th_and_5th_open_it_is_still_in_play(self):
        assert _decidido(F.FOURBALL, REVISOR, abiertos=(4, 5)) is None

    def test_d4_a_disputed_hole_after_the_decision_does_not_count(self):
        resultado = _decidido(F.FOURBALL, DECIDIDO_EN_EL_10, abiertos=(12,))
        assert resultado == {"winner": "A", "score": "10&8"}

    @pytest.mark.parametrize("formato", [F.SINGLES, F.FOURSOMES])
    def test_d6_singles_and_foursomes_follow_the_same_rule(self, formato):
        assert _decidido(formato, REVISOR, abiertos=(4, 5)) is None
        assert _decidido(formato, CERRADO) == {"winner": "A", "score": "3&2"}


async def _con_las_filas(uow, match, filas):
    await uow.matches.add(match)
    for fila in filas:
        await uow.hole_scores.add(fila)


class TestAlAnotar:
    """`SubmitHoleScoreUseCase` guarda el partido decidido tras cada golpe."""

    @pytest.mark.asyncio
    async def test_d2_with_a_gap_before_it_is_not_marked_decided(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.FOURBALL)
        await _con_las_filas(uow, match, _filas(match, REVISOR, abiertos=(4, 5)))

        await SubmitHoleScoreUseCase(uow, AsyncMock(), ScoringService())._check_decided(
            match, match.id, F.FOURBALL
        )

        assert match.is_decided is False

    @pytest.mark.asyncio
    async def test_d3_closing_the_gap_decides_it_by_the_order_of_play(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.FOURBALL)
        await _con_las_filas(uow, match, _filas(match, CERRADO))

        await SubmitHoleScoreUseCase(uow, AsyncMock(), ScoringService())._check_decided(
            match, match.id, F.FOURBALL
        )

        assert match.is_decided is True
        assert match.decided_result == {"winner": "A", "score": "3&2"}


class TestEnLaClasificacion:
    """D7: la clasificacion recalcula el resultado con la misma regla."""

    @pytest.mark.asyncio
    async def test_d7_it_does_not_take_a_decision_from_before_the_gap(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.FOURBALL)
        await _con_las_filas(uow, match, _filas(match, REVISOR, abiertos=(4, 5)))
        caso = GetLeaderboardUseCase(uow, MagicMock(), ScoringService())

        resultado = await caso._compute_decided_result(match, F.FOURBALL)

        # R1: sin decision en orden, la ventaja tal cual y no un «5&3»
        assert resultado == {"winner": "A", "score": "5UP"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("resultados", "abiertos", "esperado"),
        [(CERRADO, (), "3&2"), (DECIDIDO_EN_EL_10, (12,), "10&8")],
    )
    async def test_d7_it_is_the_same_score_that_was_stored(self, resultados, abiertos, esperado):
        uow = InMemoryUnitOfWork()
        match = _partido(F.FOURBALL)
        await _con_las_filas(uow, match, _filas(match, resultados, abiertos))
        caso = GetLeaderboardUseCase(uow, MagicMock(), ScoringService())

        resultado = await caso._compute_decided_result(match, F.FOURBALL)

        assert resultado == {"winner": "A", "score": esperado}


def _ronda(uow, match, formato):
    ronda = MagicMock()
    ronda.id = match.round_id
    ronda.match_format = formato
    ronda.status = RoundStatus.IN_PROGRESS
    ronda.competition_id = MagicMock()
    ronda.round_date = None
    ronda.session_type = MagicMock(value="MORNING")
    ronda.golf_course_id = GolfCourseId.generate()
    uow._rounds._rounds[ronda.id] = ronda
    return ronda


def _fila_de(filas, match, hoyo):
    """La fila del primer jugador de A en ese hoyo."""
    jugador = match.team_a_players[0].user_id
    return next(f for f in filas if f.hole_number == hoyo and f.player_user_id == jugador)


class TestConHuecosSinDecidir:
    @pytest.mark.asyncio
    async def test_r3_all_square_with_a_gap_is_halved(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.FOURBALL)
        empatado = dict.fromkeys((1, 2, 3, *range(6, 18)), "HALVED")
        await _con_las_filas(uow, match, _filas(match, empatado, abiertos=(4, 5)))
        caso = GetLeaderboardUseCase(uow, MagicMock(), ScoringService())

        resultado = await caso._compute_decided_result(match, F.FOURBALL)

        assert resultado == {"winner": "HALVED", "score": "AS"}

    @pytest.mark.asyncio
    async def test_r2_submitting_the_scorecards_stores_5up(self):
        """El 4 y el 5 sin anotar: la entrega no los exige, y no se inventa un N&M."""
        uow = InMemoryUnitOfWork()
        match = _partido(F.SINGLES)
        _ronda(uow, match, F.SINGLES)
        await _con_las_filas(uow, match, _filas(match, REVISOR))
        match.submit_scorecard(match.team_a_players[0].user_id, F.SINGLES)

        respuesta = await SubmitScorecardUseCase(uow, ScoringService()).execute(
            str(match.id), match.team_b_players[0].user_id
        )

        assert respuesta.match_complete is True
        assert (respuesta.result.winner, respuesta.result.score) == ("A", "5UP")


GANA_A_HASTA_EL_14 = dict.fromkeys(range(1, 15), "A")


class TestSeRecalculaAlAnotar:
    async def _decidido(self, uow, match, filas):
        await _con_las_filas(uow, match, filas)
        caso = SubmitHoleScoreUseCase(uow, AsyncMock(), ScoringService())
        await caso._check_decided(match, match.id, F.SINGLES)
        assert match.decided_result == {"winner": "A", "score": "10&8"}
        return caso

    @pytest.mark.asyncio
    async def test_r4_r6_a_dispute_before_undecides_it_until_resolved(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.SINGLES)
        filas = _filas(match, GANA_A_HASTA_EL_14)
        caso = await self._decidido(uow, match, filas)
        fila = _fila_de(filas, match, 3)

        fila.set_marker_score(5)
        fila.recalculate_validation()
        await caso._check_decided(match, match.id, F.SINGLES)
        assert (match.is_decided, match.decided_result) == (False, None)

        fila.set_marker_score(4)
        fila.recalculate_validation()
        await caso._check_decided(match, match.id, F.SINGLES)
        assert (match.is_decided, match.decided_result) == (True, {"winner": "A", "score": "10&8"})

    @pytest.mark.asyncio
    async def test_r5_a_new_winner_of_an_earlier_hole_stores_the_new_result(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.SINGLES)
        filas = _filas(match, GANA_A_HASTA_EL_14)
        caso = await self._decidido(uow, match, filas)
        fila = _fila_de(filas, match, 3)

        fila.set_own_score(6)
        fila.set_marker_score(6)
        fila.recalculate_validation()
        await caso._check_decided(match, match.id, F.SINGLES)

        assert match.decided_result == {"winner": "A", "score": "9&7"}

    @pytest.mark.asyncio
    async def test_r7_with_a_scorecard_submitted_the_decision_stays(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.SINGLES)
        filas = _filas(match, GANA_A_HASTA_EL_14)
        caso = await self._decidido(uow, match, filas)
        match.submit_scorecard(match.team_b_players[0].user_id, F.SINGLES)
        fila = _fila_de(filas, match, 3)

        fila.set_marker_score(5)
        fila.recalculate_validation()
        await caso._check_decided(match, match.id, F.SINGLES)

        assert (match.is_decided, match.decided_result) == (True, {"winner": "A", "score": "10&8"})


class TestLaPantallaDelTorneo:
    @pytest.mark.asyncio
    async def test_r8_the_scoring_view_shows_the_decision_hole(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.SINGLES)
        a, b = match.team_a_players[0].user_id, match.team_b_players[0].user_id
        match._marker_assignments = (
            MarkerAssignment(scorer_user_id=a, marks_user_id=b, marked_by_user_id=b),
            MarkerAssignment(scorer_user_id=b, marks_user_id=a, marked_by_user_id=a),
        )
        ronda = _ronda(uow, match, F.SINGLES)
        competicion = MagicMock()
        competicion.id = ronda.competition_id
        competicion.require_ryder_cup.return_value = competicion.ryder_cup
        competicion.ryder_cup.team_1_name = "A"
        competicion.ryder_cup.team_2_name = "B"
        uow._competitions._competitions[competicion.id] = competicion
        await _con_las_filas(uow, match, _filas(match, dict.fromkeys(range(1, 13), "A")))
        usuarios = AsyncMock()
        usuario = MagicMock(display_name="X")
        usuario.display_name_or_legal = MagicMock(return_value="X")
        usuarios.find_by_id = AsyncMock(return_value=usuario)
        await uow.hole_scores.add(
            HoleScore.create(
                match_id=match.id, hole_number=13, player_user_id=a, team="A", strokes_received=0
            )
        )

        vista = await SubmitHoleScoreUseCase(uow, usuarios, ScoringService()).execute(
            str(match.id), 13, SubmitHoleScoreBodyDTO(own_score=4, marked_player_id=str(b)), a
        )

        estado = vista.match_standing
        assert (estado.status, estado.leading_team, estado.holes_played) == ("10UP", "A", 10)
        assert estado.holes_remaining == 8

    @pytest.mark.asyncio
    async def test_r9_r10_the_live_leaderboard_stops_at_the_decision_hole(self):
        uow = InMemoryUnitOfWork()
        match = _partido(F.FOURBALL)
        await _con_las_filas(uow, match, _filas(match, GANA_A_HASTA_EL_14))
        caso = GetLeaderboardUseCase(uow, MagicMock(), ScoringService())
        ronda = MagicMock(match_format=F.FOURBALL)

        assert await caso._compute_in_progress_standing(match, ronda) == ("10UP", "A", 10)

        otro = _partido(F.FOURBALL)
        await _con_las_filas(uow, otro, _filas(otro, REVISOR, abiertos=(4, 5)))
        assert await caso._compute_in_progress_standing(otro, ronda) == ("5UP", "A", 15)
