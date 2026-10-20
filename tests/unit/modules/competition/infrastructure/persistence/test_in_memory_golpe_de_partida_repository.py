"""El repositorio en memoria de golpes se comporta como el de Postgres (#251, PR 5)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_golpe_de_partida_repository import (
    InMemoryGolpeDePartidaRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio

AHORA = datetime(2030, 10, 11, 9, 0, tzinfo=UTC)
COMPETICION, FRANJA, PARTIDA = CompetitionId(uuid4()), RoundId.generate(), PartidaId.generate()
JUGADOR = UserId.generate()


def _golpe(hoyo=1, partida=PARTIDA, franja=FRANJA, competicion=COMPETICION):
    return GolpeDePartida.crear(partida, franja, competicion, JUGADOR, hoyo, AHORA)


async def test_the_same_hole_is_one_row_and_what_comes_back_is_a_copy():
    repo = InMemoryGolpeDePartidaRepository()
    golpe = _golpe()
    await repo.guardar(golpe)
    golpe.anotar_propio(4, acepta_raya=False, quien=JUGADOR, momento=AHORA)
    await repo.guardar(golpe)

    (leido,) = await repo.de_la_partida(PARTIDA)
    leido.anotar_propio(9, acepta_raya=False, quien=JUGADOR, momento=AHORA)

    assert (await repo.de_la_partida(PARTIDA))[0].propio == 4


async def test_by_group_window_and_competition():
    repo = InMemoryGolpeDePartidaRepository()
    otra_franja = RoundId.generate()
    await repo.guardar(_golpe(1))
    await repo.guardar(_golpe(1, partida=PartidaId.generate(), franja=otra_franja))
    await repo.guardar(
        _golpe(
            1,
            partida=PartidaId.generate(),
            franja=RoundId.generate(),
            competicion=CompetitionId(uuid4()),
        )
    )

    assert len(await repo.de_la_partida(PARTIDA)) == 1
    assert len(await repo.de_la_franja(FRANJA)) == 1
    assert len(await repo.de_la_competicion(COMPETICION)) == 2
