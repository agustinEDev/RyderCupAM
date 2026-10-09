"""
Anotar un hoyo en una partida de stroke play (#251, PR 5; P1, P2, P3, P10, P11).

Cada uno apunta su golpe y el de quien marca; vale cuando coinciden. La
anotación abre para toda la franja a su primera salida (P1), el primer golpe
pone la partida y la competición en juego (P2), y una tarjeta entregada ya no
se toca desde aquí (P3; la corrige el organizador, P9).

| Caso                                             | Resultado                               |
|--------------------------------------------------|-----------------------------------------|
| Antes de la 1.ª salida                           | ScoringNotOpenYetError con la hora      |
| Quien no es de la partida                        | NoEsDeLaPartidaError                    |
| Marcando a quien no le toca                      | NotYourMarkedPlayerError, nada guardado |
| Primer golpe                                     | Partida y competición en juego          |
| Jugador y marcador coinciden                     | Validado                                |
| Un campo que no viene                            | No se toca                              |
| Raya en Medal / en Stableford                    | RayaNoPermitidaError / vale             |
| Hoyo 19                                          | InvalidHoleNumberError                  |
| Su tarjeta entregada                             | Su lado ignorado; el del marcado, no    |
| Partida de 1: su golpe / el de un marcado        | Vale / SinMarcadorError                 |
| Competición acabada                              | PartidaNoAnotableError                  |
| Golpe tardío en una partida acabada              | Ignorado, sigue acabada                 |
| Sin ningún golpe                                 | ValidationError: no arranca nada        |
| Con uno solo, o levantando bola                  | Se acepta                               |
| Con acting_as (anotar por otro, de la Ryder)     | ValidationError: aquí no existe         |
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.partidas_dto import SubmitTeeGroupScoreBodyDTO
from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import (
    InvalidHoleNumberError,
    NotYourMarkedPlayerError,
    ScoringNotOpenYetError,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
    NoEsDeLaPartidaError,
    PartidaNoAnotableError,
    SinMarcadorError,
)
from src.modules.competition.domain.entities.golpe_de_partida import RayaNoPermitidaError
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio

# Las 9:05 en Madrid del viernes: la franja de las 9:00 ya abrió
A_LAS_NUEVE_Y_CINCO = datetime(2030, 10, 11, 7, 5, tzinfo=UTC)
PRIMERA_SALIDA = datetime(2030, 10, 11, 7, 0, tzinfo=UTC)


async def _partida(n=3, tipo=TournamentType.STABLEFORD) -> tuple[_Escenario, Partida]:
    escenario = _Escenario()
    escenario.competicion._tournament_type = tipo
    await escenario.guardar()
    for h in range(n, 0, -1):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    (partida,) = await escenario.uow.partidas.de_la_franja(escenario.manana.id)
    escenario.ahora = A_LAS_NUEVE_Y_CINCO
    return escenario, partida


def _caso(escenario: _Escenario) -> AnotarHoyoDePartidaUseCase:
    return AnotarHoyoDePartidaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


async def _anotar(escenario, partida, quien, hoyo=1, **body):
    body.setdefault("marked_player_id", str(partida.marcadores.get(quien, quien).value))
    await _caso(escenario).execute(partida.id.value, hoyo, SubmitHoleScoreBodyDTO(**body), quien)


async def _golpes(escenario, partida) -> dict:
    return {
        (g.user_id, g.hoyo): g
        for g in await escenario.uow.golpes_de_partida.de_la_partida(partida.id)
    }


async def test_before_the_first_tee_time():
    escenario, partida = await _partida()
    escenario.ahora = datetime(2030, 10, 11, 6, 59, tzinfo=UTC)

    with pytest.raises(ScoringNotOpenYetError) as error:
        await _anotar(escenario, partida, partida.user_ids[0], own_score=4)

    assert error.value.opens_at == PRIMERA_SALIDA


async def test_someone_not_in_the_group():
    escenario, partida = await _partida()

    with pytest.raises(NoEsDeLaPartidaError):
        await _anotar(escenario, partida, UserId.generate(), own_score=4)


async def test_marking_someone_else_saves_nothing():
    escenario, partida = await _partida()
    a, _, c = partida.user_ids  # a marca a b

    with pytest.raises(NotYourMarkedPlayerError):
        await _anotar(
            escenario, partida, a, own_score=4, marked_player_id=str(c.value), marked_score=5
        )

    assert await _golpes(escenario, partida) == {}


async def test_the_first_score_puts_group_and_competition_in_play():
    escenario, partida = await _partida()
    a, b, _ = partida.user_ids

    await _anotar(escenario, partida, a, own_score=4, marked_score=5)

    golpes = await _golpes(escenario, partida)
    assert (golpes[(a, 1)].propio, golpes[(b, 1)].del_marcador) == (4, 5)
    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.IN_PROGRESS
    assert escenario.competicion.status == CompetitionStatus.IN_PROGRESS


async def test_player_and_marker_agree():
    escenario, partida = await _partida()
    a, b, _ = partida.user_ids

    await _anotar(escenario, partida, a, own_score=4, marked_score=5)
    await _anotar(escenario, partida, b, own_score=5)

    assert (await _golpes(escenario, partida))[(b, 1)].validado


async def test_a_field_that_does_not_come_is_not_touched():
    escenario, partida = await _partida()
    a, b, _ = partida.user_ids

    await _anotar(escenario, partida, a, marked_score=5)

    golpes = await _golpes(escenario, partida)
    assert (a, 1) not in golpes
    assert golpes[(b, 1)].del_marcador == 5


async def test_no_pick_up_in_medal_and_nothing_saved():
    escenario, partida = await _partida(tipo=TournamentType.MEDAL)

    with pytest.raises(RayaNoPermitidaError):
        await _anotar(escenario, partida, partida.user_ids[0], own_score=None)

    assert await _golpes(escenario, partida) == {}
    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.SCHEDULED


async def test_a_pick_up_in_stableford():
    escenario, partida = await _partida()
    a = partida.user_ids[0]

    await _anotar(escenario, partida, a, own_score=None)

    golpe = (await _golpes(escenario, partida))[(a, 1)]
    assert golpe.propio_enviado and golpe.propio is None


async def test_hole_nineteen():
    escenario, partida = await _partida()

    with pytest.raises(InvalidHoleNumberError):
        await _anotar(escenario, partida, partida.user_ids[0], hoyo=19, own_score=4)


async def test_a_delivered_card_ignores_its_side_but_not_the_marked_one():
    escenario, partida = await _partida()
    a, b, _ = partida.user_ids
    await _anotar(escenario, partida, a, own_score=4)
    abierta = await escenario.uow.partidas.find_by_id(partida.id)
    abierta.entregar(a)
    await escenario.uow.partidas.guardar([abierta])

    await _anotar(escenario, partida, a, own_score=7, marked_score=5)

    golpes = await _golpes(escenario, partida)
    assert golpes[(a, 1)].propio == 4
    assert golpes[(b, 1)].del_marcador == 5


async def test_a_group_of_one():
    escenario, partida = await _partida(n=2)
    a, b = partida.user_ids
    sola = await escenario.uow.partidas.find_by_id(partida.id)
    sola.quitar(b)
    await escenario.uow.partidas.guardar([sola])

    await _anotar(escenario, sola, a, own_score=4)
    with pytest.raises(SinMarcadorError):
        await _anotar(escenario, sola, a, own_score=4, marked_score=4)

    assert (await _golpes(escenario, sola))[(a, 1)].propio == 4


async def test_a_finished_competition():
    escenario, partida = await _partida()
    escenario.competicion._status = CompetitionStatus.COMPLETED

    with pytest.raises(PartidaNoAnotableError):
        await _anotar(escenario, partida, partida.user_ids[0], own_score=4)


async def test_a_late_score_on_a_finished_group():
    escenario, partida = await _partida(n=2)
    a, b = partida.user_ids
    await _anotar(escenario, partida, a, own_score=4)
    acabada = await escenario.uow.partidas.find_by_id(partida.id)
    acabada.entregar(a)
    acabada.entregar(b)
    await escenario.uow.partidas.guardar([acabada])

    await _anotar(escenario, partida, b, own_score=6, marked_score=6)

    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.COMPLETED
    assert (await _golpes(escenario, partida))[(a, 1)].del_marcador is None


def test_a_score_without_any_stroke():
    # Arrancaba la partida y la competición sin escribir nada
    with pytest.raises(ValidationError):
        SubmitTeeGroupScoreBodyDTO(marked_player_id="x")


@pytest.mark.parametrize("golpes", [{"own_score": None}, {"marked_score": 4}])
def test_a_score_with_one_stroke(golpes):
    body = SubmitTeeGroupScoreBodyDTO(marked_player_id="x", **golpes)

    assert body.model_fields_set == {"marked_player_id", *golpes}


def test_acting_as_does_not_exist_here():
    # Se ignoraba: el admin anotaba como él mismo sin enterarse
    with pytest.raises(ValidationError):
        SubmitTeeGroupScoreBodyDTO(
            marked_player_id="x", own_score=4, acting_as="11111111-1111-1111-1111-111111111111"
        )
