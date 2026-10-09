"""
Entregar la tarjeta y retirarse de una partida (#251, PR 5; P3, P4, P6).

| Caso                                    | Resultado                                  |
|-----------------------------------------|--------------------------------------------|
| Los 18 validados                        | ENTREGADA; con todas, la partida acaba     |
| Hoyos sin validar                       | TarjetaIncompletaError con esos hoyos (P4) |
| Sin empezar / dos veces                 | PartidaNoEmpezadaError / TarjetaCerrada    |
| Quien no es de la partida               | NoEsDeLaPartidaError                       |
| Retirarse                               | RETIRADO                                   |
"""

import pytest

from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    NoEsDeLaPartidaError,
)
from src.modules.competition.application.use_cases.entregar_tarjeta_de_partida_use_case import (
    EntregarTarjetaDePartidaUseCase,
    RetirarseDePartidaUseCase,
    TarjetaIncompletaError,
)
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.partida import (
    PartidaNoEmpezadaError,
    TarjetaCerradaError,
)
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
    _partida,
)

pytestmark = pytest.mark.asyncio


async def _en_juego(n=2):
    escenario, partida = await _partida(n=n)
    en_juego = await escenario.uow.partidas.find_by_id(partida.id)
    en_juego.empezar()
    await escenario.uow.partidas.guardar([en_juego])
    return escenario, en_juego


async def _validar(escenario, partida, user_id, hoyos=range(1, 19), golpes=4):
    for hoyo in hoyos:
        golpe = GolpeDePartida.crear(
            partida.id, partida.round_id, partida.competition_id, user_id, hoyo, A_LAS_NUEVE_Y_CINCO
        )
        golpe.anotar_propio(golpes, False, user_id, A_LAS_NUEVE_Y_CINCO)
        golpe.anotar_del_marcador(golpes, False, partida.marcadores[user_id], A_LAS_NUEVE_Y_CINCO)
        await escenario.uow.golpes_de_partida.guardar(golpe)


def _entregar(escenario):
    return EntregarTarjetaDePartidaUseCase(uow=escenario.uow)


async def _estado(escenario, partida):
    return await escenario.uow.partidas.find_by_id(partida.id)


async def test_all_eighteen_validated_and_then_the_group_finishes():
    escenario, partida = await _en_juego()
    a, b = partida.user_ids
    await _validar(escenario, partida, a)
    await _validar(escenario, partida, b)

    await _entregar(escenario).execute(partida.id.value, a)
    assert (await _estado(escenario, partida)).estado == EstadoPartida.IN_PROGRESS
    await _entregar(escenario).execute(partida.id.value, b)

    despues = await _estado(escenario, partida)
    assert despues.estados_de_tarjeta[a] == EstadoDeTarjeta.ENTREGADA
    assert despues.estado == EstadoPartida.COMPLETED


async def test_holes_not_validated():
    escenario, partida = await _en_juego()
    a = partida.user_ids[0]
    await _validar(escenario, partida, a, hoyos=range(1, 17))

    with pytest.raises(TarjetaIncompletaError) as error:
        await _entregar(escenario).execute(partida.id.value, a)

    assert error.value.hoyos == [17, 18]
    assert (await _estado(escenario, partida)).estados_de_tarjeta[a] == EstadoDeTarjeta.JUGANDO


async def test_not_started_and_twice():
    escenario, partida = await _partida(n=2)
    a = partida.user_ids[0]
    await _validar(escenario, partida, a)
    with pytest.raises(PartidaNoEmpezadaError):
        await _entregar(escenario).execute(partida.id.value, a)

    escenario, partida = await _en_juego()
    a = partida.user_ids[0]
    await _validar(escenario, partida, a)
    await _entregar(escenario).execute(partida.id.value, a)
    with pytest.raises(TarjetaCerradaError):
        await _entregar(escenario).execute(partida.id.value, a)


async def test_someone_not_in_the_group():
    escenario, partida = await _en_juego()

    with pytest.raises(NoEsDeLaPartidaError):
        await _entregar(escenario).execute(partida.id.value, UserId.generate())


async def test_retiring():
    escenario, partida = await _en_juego()
    a = partida.user_ids[0]

    await RetirarseDePartidaUseCase(uow=escenario.uow).execute(partida.id.value, a)

    assert (await _estado(escenario, partida)).estados_de_tarjeta[a] == EstadoDeTarjeta.RETIRADO


async def test_a_hole_where_player_and_marker_disagree():
    escenario, partida = await _en_juego()
    a = partida.user_ids[0]
    await _validar(escenario, partida, a, hoyos=range(1, 18))
    golpe = GolpeDePartida.crear(
        partida.id, partida.round_id, partida.competition_id, a, 18, A_LAS_NUEVE_Y_CINCO
    )
    golpe.anotar_propio(4, False, a, A_LAS_NUEVE_Y_CINCO)
    golpe.anotar_del_marcador(5, False, partida.marcadores[a], A_LAS_NUEVE_Y_CINCO)
    await escenario.uow.golpes_de_partida.guardar(golpe)

    with pytest.raises(TarjetaIncompletaError) as error:
        await _entregar(escenario).execute(partida.id.value, a)

    assert error.value.hoyos == [18]
