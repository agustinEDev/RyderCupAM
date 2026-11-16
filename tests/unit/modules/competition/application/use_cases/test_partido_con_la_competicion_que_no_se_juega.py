"""
Match play con la competición fuera de juego (SB-03, decidido el 16 nov 2026).

Un partido ya abierto se seguía anotando, concediendo y entregando aunque el
organizador hubiera terminado o cancelado la competición: solo se miraba el estado
del partido. Ahora manda la misma regla que en el stroke play, una sola en el
dominio: se anota mientras la competición «se está jugando», cerrada o en juego.

| estado de la competición | anotar / conceder / entregar / retirar |
|--------------------------|----------------------------------------|
| CLOSED, IN_PROGRESS      | como siempre                           |
| ACTIVE, COMPLETED,       | MatchNotScoringError (409) y el        |
| CANCELLED                | partido se queda como estaba           |
"""

import pytest

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import MatchNotScoringError
from src.modules.competition.application.use_cases.concede_match_use_case import (
    ConcedeMatchUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from tests.unit.modules.competition.application.use_cases.test_fourball_withdrawn_player import (
    _Escena,
    _filas_del_hoyo_1,
    _usuarios,
)

pytestmark = pytest.mark.asyncio

SE_JUEGA = [CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS]
NO_SE_JUEGA = [CompetitionStatus.ACTIVE, CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED]


async def _escena(estado: CompetitionStatus) -> _Escena:
    """Un fourball ya abierto, con las filas del hoyo 1 y la competición en `estado`."""
    e = _Escena()
    e.uow.competitions.find_by_id.return_value.status = estado
    await e.guardar(_filas_del_hoyo_1(e))
    return e


def _golpe(e: _Escena) -> SubmitHoleScoreBodyDTO:
    marcado = next(a.marks_user_id for a in e.match.marker_assignments if a.scorer_user_id == e.a1)
    return SubmitHoleScoreBodyDTO(own_score=4, marked_player_id=str(marcado), marked_score=5)


class TestAnotarUnHoyo:
    @pytest.mark.parametrize("estado", NO_SE_JUEGA)
    async def test_no_se_anota_si_la_competicion_no_se_juega(self, estado):
        """
        Given un partido abierto y la competición en ACTIVE, COMPLETED o CANCELLED
        When un jugador anota un hoyo
        Then 409 y el hoyo se queda sin anotar
        """
        e = await _escena(estado)

        with pytest.raises(MatchNotScoringError):
            await SubmitHoleScoreUseCase(e.uow, _usuarios(), ScoringService()).execute(
                str(e.match.id), 1, _golpe(e), e.a1
            )

        assert (await e.uow.hole_scores.find_one(e.match.id, 1, e.a1)).own_score is None

    @pytest.mark.parametrize("estado", SE_JUEGA)
    async def test_se_anota_si_la_competicion_se_juega(self, estado):
        """Given la competición cerrada o en juego / When anota / Then se guarda."""
        e = await _escena(estado)

        await SubmitHoleScoreUseCase(e.uow, _usuarios(), ScoringService()).execute(
            str(e.match.id), 1, _golpe(e), e.a1
        )

        assert (await e.uow.hole_scores.find_one(e.match.id, 1, e.a1)).own_score == 4


class TestConceder:
    @pytest.mark.parametrize("estado", NO_SE_JUEGA)
    async def test_no_se_concede_si_la_competicion_no_se_juega(self, estado):
        """Given la competición fuera de juego / When un jugador concede / Then 409 y sigue abierto."""
        e = await _escena(estado)

        with pytest.raises(MatchNotScoringError):
            await ConcedeMatchUseCase(e.uow, ScoringService()).execute(str(e.match.id), e.a1, "A")

        assert (await e.partido()).status == MatchStatus.IN_PROGRESS

    @pytest.mark.parametrize("estado", SE_JUEGA)
    async def test_se_concede_si_la_competicion_se_juega(self, estado):
        """Given la competición cerrada o en juego / When concede / Then el partido se concede."""
        e = await _escena(estado)

        await ConcedeMatchUseCase(e.uow, ScoringService()).execute(str(e.match.id), e.a1, "A")

        assert (await e.partido()).status == MatchStatus.CONCEDED


class TestEntregarLaTarjeta:
    @pytest.mark.parametrize("estado", NO_SE_JUEGA)
    async def test_no_se_entrega_si_la_competicion_no_se_juega(self, estado):
        """Given la competición fuera de juego / When entrega la tarjeta / Then 409 y sin entregar."""
        e = await _escena(estado)

        with pytest.raises(MatchNotScoringError):
            await SubmitScorecardUseCase(e.uow, ScoringService()).execute(str(e.match.id), e.a1)

        assert not (await e.partido()).scorecard_submitted_by

    @pytest.mark.parametrize("estado", SE_JUEGA)
    async def test_se_entrega_si_la_competicion_se_juega(self, estado):
        """Given la competición cerrada o en juego / When entrega / Then queda entregada."""
        e = await _escena(estado)

        await SubmitScorecardUseCase(e.uow, ScoringService()).execute(str(e.match.id), e.a1)

        assert (await e.partido()).scorecard_submitted_by


class TestCerrarUnPartidoConTodasLasTarjetas:
    """
    Decisión del dueño (16 nov 2026): un partido abierto que ya tiene todas sus tarjetas
    entregadas (el caso de la BE #377) se puede CERRAR aunque la competición ya no se
    juegue. Solo cerrar: ni golpes ni tarjetas nuevas.
    """

    @staticmethod
    async def _con_todas_las_tarjetas(estado: CompetitionStatus) -> _Escena:
        e = _Escena()
        e.uow.competitions.find_by_id.return_value.status = estado
        jugadores = [p.user_id for p in e.match.team_a_players + e.match.team_b_players]
        for jugador in jugadores:
            e.match.submit_scorecard(jugador, e.ronda.match_format)
        assert e.match.all_scorecards_submitted(e.ronda.match_format)
        assert e.match.status == MatchStatus.IN_PROGRESS
        await e.guardar(_filas_del_hoyo_1(e))
        return e

    @pytest.mark.parametrize("estado", NO_SE_JUEGA + SE_JUEGA)
    async def test_se_cierra_aunque_la_competicion_no_se_juegue(self, estado):
        e = await self._con_todas_las_tarjetas(estado)

        respuesta = await SubmitScorecardUseCase(e.uow, ScoringService()).execute(
            str(e.match.id), e.a1
        )

        assert respuesta.match_complete is True
        assert (await e.partido()).status == MatchStatus.COMPLETED

    @pytest.mark.parametrize("estado", NO_SE_JUEGA)
    async def test_pero_no_admite_golpes(self, estado):
        e = await self._con_todas_las_tarjetas(estado)

        with pytest.raises(MatchNotScoringError):
            await SubmitHoleScoreUseCase(e.uow, _usuarios(), ScoringService()).execute(
                str(e.match.id), 1, _golpe(e), e.a1
            )

    @pytest.mark.parametrize("estado", NO_SE_JUEGA)
    async def test_con_una_tarjeta_sin_entregar_sigue_el_409(self, estado):
        e = _Escena()
        e.uow.competitions.find_by_id.return_value.status = estado
        jugadores = [p.user_id for p in e.match.team_a_players + e.match.team_b_players]
        for jugador in jugadores[1:]:
            e.match.submit_scorecard(jugador, e.ronda.match_format)
        await e.guardar(_filas_del_hoyo_1(e))

        with pytest.raises(MatchNotScoringError):
            await SubmitScorecardUseCase(e.uow, ScoringService()).execute(str(e.match.id), e.a1)

        assert (await e.partido()).status == MatchStatus.IN_PROGRESS


class TestRetirarAUnJugador:
    """Retirar o devolver a un jugador cambia la decisión del partido: también es puntuación."""

    @pytest.mark.parametrize("estado", NO_SE_JUEGA)
    async def test_no_se_retira_si_la_competicion_no_se_juega(self, estado):
        """Given la competición fuera de juego / When su pareja le retira / Then 409 y sigue jugando."""
        e = await _escena(estado)

        with pytest.raises(MatchNotScoringError):
            await e.retirar(e.a1, e.a2)

        assert not (await e.partido()).withdrawn_player_ids

    @pytest.mark.parametrize("estado", NO_SE_JUEGA)
    async def test_no_se_devuelve_si_la_competicion_no_se_juega(self, estado):
        """Given un retirado y la competición fuera de juego / When le devuelven / Then 409."""
        e = _Escena()
        e.uow.competitions.find_by_id.return_value.status = estado
        e.match.withdraw_player(e.a1, e.ronda.match_format)
        await e.guardar(_filas_del_hoyo_1(e))

        with pytest.raises(MatchNotScoringError):
            await e.retirar(e.a1, e.a2, deshacer=True)

        assert e.a1 in (await e.partido()).withdrawn_player_ids

    @pytest.mark.parametrize("estado", SE_JUEGA)
    async def test_se_retira_si_la_competicion_se_juega(self, estado):
        """Given la competición cerrada o en juego / When le retiran / Then queda retirado."""
        e = await _escena(estado)

        await e.retirar(e.a1, e.a2)

        assert e.a1 in (await e.partido()).withdrawn_player_ids


class TestLaRegla:
    """Una sola regla en el dominio para stroke play y match play."""

    @pytest.mark.parametrize("estado", list(CompetitionStatus))
    def test_se_anota_solo_cerrada_o_en_juego(self, estado):
        assert estado.admite_anotar() is (estado in SE_JUEGA)


class TestStrokePlayConLaFilaBloqueada:
    """
    El stroke play relee la competición con su fila bloqueada antes de ponerla en juego:
    si entre la primera lectura y el bloqueo la terminaron, cancelaron o reabrieron,
    el golpe no entra (la misma regla, con el error del stroke play).
    """

    @pytest.mark.parametrize("estado", NO_SE_JUEGA)
    async def test_si_al_bloquearla_ya_no_se_juega_no_se_arranca(self, estado):
        from unittest.mock import AsyncMock, MagicMock

        from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
            PartidaNoAnotableError,
            arrancar_la_competicion,
        )

        leida = MagicMock(status=CompetitionStatus.CLOSED)
        bloqueada = MagicMock(status=estado)
        uow = MagicMock()
        uow.competitions.find_by_id_for_update = AsyncMock(return_value=bloqueada)
        uow.competitions.update = AsyncMock()

        with pytest.raises(PartidaNoAnotableError):
            await arrancar_la_competicion(uow, leida)

        bloqueada.start.assert_not_called()
        uow.competitions.update.assert_not_called()
