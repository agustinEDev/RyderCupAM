"""
Lo jugado de un stroke play también se protege (#251, PR 5).

Un golpe apuntado en una partida es jugado: la competición no se borra y la
franja tampoco. Generar las partidas no es jugar.

| Caso                                   | Resultado |
|----------------------------------------|-----------|
| Partidas generadas, sin golpes         | No jugado |
| Un golpe apuntado (aunque sin validar) | Jugado    |
| Preguntando para borrar (bloquear)     | Bloquea cada partida ANTES de leer sus golpes |
| La competición entera                  | Lee los golpes una sola vez, no por franja    |
"""

import pytest

from src.modules.competition.application.services.lo_jugado import LoJugado
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_golpe_de_partida_repository import (
    InMemoryGolpeDePartidaRepository,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_partida_repository import (
    InMemoryPartidaRepository,
)
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
    _partida,
)

pytestmark = pytest.mark.asyncio


async def test_generated_groups_are_not_played():
    escenario, _ = await _partida()

    assert not await LoJugado(escenario.uow).en_la_sesion(escenario.manana.id)
    assert not await LoJugado(escenario.uow).en_la_competicion(escenario.competicion.id)


async def test_one_score_entered_is_played():
    escenario, partida = await _partida()
    a = partida.user_ids[0]
    golpe = GolpeDePartida.crear(
        partida.id, partida.round_id, partida.competition_id, a, 1, A_LAS_NUEVE_Y_CINCO
    )
    golpe.anotar_propio(4, True, a, A_LAS_NUEVE_Y_CINCO)
    await escenario.uow.golpes_de_partida.guardar(golpe)

    assert await LoJugado(escenario.uow).en_la_sesion(escenario.manana.id)
    assert await LoJugado(escenario.uow).en_la_competicion(escenario.competicion.id, bloquear=True)


def _apuntar_lecturas(monkeypatch) -> list[str]:
    """Qué se lee y en qué orden: bloquear partidas, golpes de franja o de competición."""
    lecturas: list[str] = []
    for clase, metodo in (
        (InMemoryPartidaRepository, "find_by_id_for_update"),
        (InMemoryGolpeDePartidaRepository, "de_la_franja"),
        (InMemoryGolpeDePartidaRepository, "de_la_competicion"),
    ):
        original = getattr(clase, metodo)

        async def apuntado(self, *args, _original=original, _metodo=metodo):
            lecturas.append(_metodo)
            return await _original(self, *args)

        monkeypatch.setattr(clase, metodo, apuntado)
    return lecturas


@pytest.mark.parametrize("pregunta", ["en_la_sesion", "en_la_competicion"])
async def test_locks_each_group_before_reading_its_scores(pregunta, monkeypatch):
    # Sin el bloqueo, un primer golpe sin confirmar no se ve, el borrado se
    # lleva al jugador y su golpe revienta la clave ajena: un 500
    escenario, _ = await _partida()
    lecturas = _apuntar_lecturas(monkeypatch)
    donde = escenario.manana.id if pregunta == "en_la_sesion" else escenario.competicion.id

    await getattr(LoJugado(escenario.uow), pregunta)(donde, bloquear=True)

    assert lecturas[0] == "find_by_id_for_update"


async def test_the_competition_reads_its_scores_once(monkeypatch):
    escenario, _ = await _partida()
    lecturas = _apuntar_lecturas(monkeypatch)

    await LoJugado(escenario.uow).en_la_competicion(escenario.competicion.id)

    assert [lectura for lectura in lecturas if lectura.startswith("de_la_")] == [
        "de_la_competicion"
    ]
