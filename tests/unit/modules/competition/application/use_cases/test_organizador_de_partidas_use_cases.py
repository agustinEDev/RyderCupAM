"""
Lo que hace el organizador con la anotación de las partidas (#251, PR 5; P3, P4, P6, P9, P11).

| Caso                                              | Resultado                              |
|---------------------------------------------------|----------------------------------------|
| Corregir siendo jugador                           | NotCompetitionCreatorError             |
| Corregir los dos lados                            | Validado, metido por él                |
| Partida de 1: el jugador y él de marcador         | Validado (P11)                         |
| Antes de la 1.ª salida                            | ScoringNotOpenYetError                 |
| Una tarjeta entregada                             | TarjetaCerradaError: se reabre antes   |
| Raya en Medal                                     | RayaNoPermitidaError                   |
| En una partida sin empezar                        | La empieza                             |
| Reabrir una entregada                             | JUGANDO                                |
| No presentado                                     | NO_PRESENTADO                          |
| Cerrar la franja                                  | Completa ENTREGADA, a medias RETIRADO, |
|                                                   | sin hoyos NO_PRESENTADO                |
| Cerrar la franja siendo jugador                   | NotCompetitionCreatorError             |
| Cerrar la franja antes de su 1.ª salida           | ScoringNotOpenYetError: nada cambia    |
| Cerrar la franja con la competición sin jugarse   | PartidaNoAnotableError                 |
| Cerrar la franja                                  | Relee cada partida bloqueándola        |
| Reabrir / no presentado con el torneo acabado     | PartidaNoAnotableError                 |
| Reabrir / no presentado antes de la 1.ª salida    | ScoringNotOpenYetError                 |
| Corregir sin ningún lado                          | ValidationError: no toca nada          |
| Corregir con un lado nulo (raya)                  | Se acepta                              |
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.partidas_dto import CorrectHoleBodyDTO
from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    ScoringNotOpenYetError,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    PartidaNoAnotableError,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    CerrarFranjaUseCase,
    CorregirHoyoDePartidaUseCase,
    MarcarNoPresentadoUseCase,
    ReabrirTarjetaUseCase,
)
from src.modules.competition.domain.entities.golpe_de_partida import RayaNoPermitidaError
from src.modules.competition.domain.entities.partida import TarjetaCerradaError
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    _partida,
)
from tests.unit.modules.competition.application.use_cases.test_entregar_tarjeta_de_partida_use_case import (
    _en_juego,
    _validar,
    con_estado,
)

pytestmark = pytest.mark.asyncio


def _corregir(escenario):
    return CorregirHoyoDePartidaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


def _reabrir(escenario):
    return ReabrirTarjetaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


def _no_presentado(escenario):
    return MarcarNoPresentadoUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


async def _corrige(escenario, partida, jugador, hoyo=1, quien=None, **body):
    await _corregir(escenario).execute(
        partida.id.value,
        jugador.value,
        hoyo,
        CorrectHoleBodyDTO(**body),
        quien or escenario.creador,
        False,
    )


async def _golpe(escenario, partida, jugador, hoyo=1):
    golpes = await escenario.uow.golpes_de_partida.de_la_partida(partida.id)
    return next(g for g in golpes if g.user_id == jugador and g.hoyo == hoyo)


async def _tarjetas(escenario, partida):
    return (await escenario.uow.partidas.find_by_id(partida.id)).estados_de_tarjeta


async def test_a_player_cannot_correct():
    escenario, partida = await _partida()
    a, b, _ = partida.user_ids

    with pytest.raises(NotCompetitionCreatorError):
        await _corrige(escenario, partida, b, quien=a, own_score=4)


async def test_both_sides_validate_and_say_who():
    escenario, partida = await _partida()
    a = partida.user_ids[0]

    await _corrige(escenario, partida, a, own_score=5, marker_score=5)

    golpe = await _golpe(escenario, partida, a)
    assert golpe.validado and golpe.golpes_validados == 5
    assert golpe.propio_por == golpe.marcador_por == escenario.creador


async def test_a_group_of_one_validated_by_the_organiser():
    escenario, partida = await _partida(n=2)
    a, b = partida.user_ids
    sola = await escenario.uow.partidas.find_by_id(partida.id)
    sola.quitar(b)
    await escenario.uow.partidas.guardar([sola])
    await _corrige(escenario, sola, a, own_score=4)

    await _corrige(escenario, sola, a, marker_score=4)

    assert (await _golpe(escenario, sola, a)).validado


async def test_before_the_first_tee_time():
    escenario, partida = await _partida()
    escenario.ahora = datetime(2030, 10, 11, 6, 0, tzinfo=UTC)

    with pytest.raises(ScoringNotOpenYetError):
        await _corrige(escenario, partida, partida.user_ids[0], own_score=4)


async def test_a_delivered_card_has_to_be_reopened_first():
    escenario, partida = await _en_juego()
    a = partida.user_ids[0]
    entregada = await escenario.uow.partidas.find_by_id(partida.id)
    entregada.entregar(a)
    await escenario.uow.partidas.guardar([entregada])

    with pytest.raises(TarjetaCerradaError):
        await _corrige(escenario, partida, a, own_score=4)
    await _reabrir(escenario).execute(partida.id.value, a.value, escenario.creador, False)
    await _corrige(escenario, partida, a, own_score=4)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.JUGANDO
    assert (await _golpe(escenario, partida, a)).propio == 4


async def test_no_pick_up_in_medal():
    escenario, partida = await _partida(tipo=TournamentType.MEDAL)

    with pytest.raises(RayaNoPermitidaError):
        await _corrige(escenario, partida, partida.user_ids[0], own_score=None)

    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.SCHEDULED


async def test_it_starts_a_group_not_started():
    escenario, partida = await _partida()

    await _corrige(escenario, partida, partida.user_ids[0], own_score=4)

    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.IN_PROGRESS


async def test_no_show():
    escenario, partida = await _partida()
    a = partida.user_ids[0]

    await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.NO_PRESENTADO


async def test_closing_the_window():
    escenario, partida = await _en_juego(n=4)
    completa, a_medias, sin_hoyos, entregada = partida.user_ids
    await _validar(escenario, partida, completa)
    await _validar(escenario, partida, a_medias, hoyos=range(1, 10))
    await _validar(escenario, partida, entregada)
    antes = await escenario.uow.partidas.find_by_id(partida.id)
    antes.entregar(entregada)
    await escenario.uow.partidas.guardar([antes])

    await CerrarFranjaUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    ).execute(escenario.manana.id.value, escenario.creador, False)

    assert await _tarjetas(escenario, partida) == {
        completa: EstadoDeTarjeta.ENTREGADA,
        a_medias: EstadoDeTarjeta.RETIRADO,
        sin_hoyos: EstadoDeTarjeta.NO_PRESENTADO,
        entregada: EstadoDeTarjeta.ENTREGADA,
    }
    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.COMPLETED


def _cerrar(escenario, quien=None):
    return CerrarFranjaUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    ).execute(escenario.manana.id.value, quien or escenario.creador, False)


async def test_closing_before_the_first_tee_time():
    # Dejaba a todos no presentados y la franja sin poder rehacerse
    escenario, partida = await _partida()
    escenario.ahora = datetime(2030, 10, 11, 6, 59, tzinfo=UTC)

    with pytest.raises(ScoringNotOpenYetError):
        await _cerrar(escenario)

    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.SCHEDULED


async def test_closing_with_the_competition_not_in_play():
    escenario, _ = await _partida()
    competicion = await escenario.uow.competitions.find_by_id(escenario.competicion.id)
    competicion._status = CompetitionStatus.ACTIVE
    await escenario.uow.competitions.update(competicion)

    with pytest.raises(PartidaNoAnotableError):
        await _cerrar(escenario)


async def test_closing_locks_each_group_before_deciding():
    # Sin bloquear, un 18 anotado a la vez quedaba como retirado
    escenario, partida = await _en_juego()
    bloqueadas = []
    original = escenario.uow.partidas.find_by_id_for_update

    async def espia(partida_id):
        bloqueadas.append(partida_id)
        return await original(partida_id)

    escenario.uow.partidas.find_by_id_for_update = espia

    await _cerrar(escenario)

    assert bloqueadas == [partida.id]


async def test_a_player_cannot_close_the_window():
    escenario, partida = await _en_juego()

    with pytest.raises(NotCompetitionCreatorError):
        await CerrarFranjaUseCase(
            uow=escenario.uow,
            zonas=escenario.zonas,
            user_repository=escenario.usuarios,
            reloj=lambda: escenario.ahora,
        ).execute(escenario.manana.id.value, partida.user_ids[0], False)


def test_a_correction_without_any_side():
    # Vacía arrancaría la partida y dejaría un golpe sin nada que impide
    # borrar la franja
    with pytest.raises(ValidationError):
        CorrectHoleBodyDTO()


@pytest.mark.parametrize("cuerpo", [{"own_score": None}, {"marker_score": 4}])
def test_a_correction_with_one_side(cuerpo):
    assert CorrectHoleBodyDTO(**cuerpo).model_fields_set == set(cuerpo)


@pytest.mark.parametrize("caso", [_reabrir, _no_presentado])
async def test_not_once_the_competition_is_over_either(caso):
    escenario, partida = await _en_juego()
    a = partida.user_ids[0]
    await con_estado(escenario, CompetitionStatus.COMPLETED)

    with pytest.raises(PartidaNoAnotableError):
        await caso(escenario).execute(partida.id.value, a.value, escenario.creador, False)


@pytest.mark.parametrize("caso", [_reabrir, _no_presentado])
async def test_not_before_the_first_tee_time_either(caso):
    # Un no presentado puesto antes de salir ignoraba luego sus golpes en silencio
    escenario, partida = await _partida()
    a = partida.user_ids[0]
    escenario.ahora = datetime(2030, 10, 11, 6, 59, tzinfo=UTC)

    with pytest.raises(ScoringNotOpenYetError):
        await caso(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.JUGANDO
