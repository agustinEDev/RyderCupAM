"""
El repositorio en memoria de partidas se comporta como el de Postgres (#251, PR 4).

Mismos casos que `test_partida_repository.py` (integración), y uno propio: guarda
y devuelve copias, así que un caso de uso que cambia una partida y no la guarda
se nota en los tests.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_partida_repository import (
    InMemoryPartidaRepository,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio

COMPETICION = CompetitionId(uuid4())
MANANA, TARDE = RoundId.generate(), RoundId.generate()
A, B, C, D, FUERA = (UserId.generate() for _ in range(5))


def _jugador(user_id: UserId) -> JugadorDePartida:
    return JugadorDePartida(user_id, Decimal("0.0"), 0, TeeColor.YELLOW, None, (0,) * 18)


def _partida(round_id: RoundId, numero: int, user_ids: list[UserId]) -> Partida:
    return Partida.crear(COMPETICION, round_id, numero, [_jugador(u) for u in user_ids])


async def test_what_comes_back_is_a_copy_until_it_is_saved():
    repo = InMemoryPartidaRepository()
    partida = _partida(MANANA, 1, [A, B])
    await repo.reemplazar_franja(MANANA, [partida])

    partida.renumerar(9)
    leida = await repo.find_by_id(partida.id)
    leida.renumerar(5)

    assert (await repo.find_by_id(partida.id)).numero == 1
    await repo.guardar([leida])
    assert (await repo.find_by_id(partida.id)).numero == 5


async def test_replacing_a_window_keeps_only_the_new_ones_and_not_the_other_window():
    repo = InMemoryPartidaRepository()
    await repo.reemplazar_franja(MANANA, [_partida(MANANA, 1, [A, B])])
    de_tarde = _partida(TARDE, 1, [C, D])
    await repo.reemplazar_franja(TARDE, [de_tarde])
    nueva = _partida(MANANA, 1, [B, A])

    await repo.reemplazar_franja(MANANA, [nueva])

    assert [p.id for p in await repo.de_la_franja(MANANA)] == [nueva.id]
    assert [p.id for p in await repo.de_la_franja(TARDE)] == [de_tarde.id]


async def test_saving_does_not_bring_back_a_deleted_one():
    repo = InMemoryPartidaRepository()
    partida = _partida(MANANA, 1, [A, B])
    await repo.reemplazar_franja(MANANA, [partida])

    await repo.borrar([partida])
    await repo.guardar([partida])

    assert await repo.find_by_id(partida.id) is None
    assert await repo.de_la_franja(MANANA) == []


async def test_queries():
    repo = InMemoryPartidaRepository()
    manana = [_partida(MANANA, 2, [C, D]), _partida(MANANA, 1, [A, B])]
    tarde = [_partida(TARDE, 1, [A, C])]
    otra_franja = RoundId.generate()
    de_otra_competicion = Partida.crear(
        CompetitionId(uuid4()), otra_franja, 1, [_jugador(A), _jugador(B)]
    )
    await repo.reemplazar_franja(MANANA, manana)
    await repo.reemplazar_franja(TARDE, tarde)
    await repo.reemplazar_franja(otra_franja, [de_otra_competicion])

    assert [p.numero for p in await repo.de_la_franja(MANANA)] == [1, 2]
    assert len(await repo.de_la_competicion(COMPETICION)) == 3
    assert await repo.de_la_competicion(CompetitionId(uuid4())) == []
    assert {p.id for p in await repo.del_jugador(COMPETICION, A)} == {manana[1].id, tarde[0].id}
    assert await repo.del_jugador(COMPETICION, FUERA) == []
    assert await repo.existe_con_jugador(A)
    assert not await repo.existe_con_jugador(FUERA)
