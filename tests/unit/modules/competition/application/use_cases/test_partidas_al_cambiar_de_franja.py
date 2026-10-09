"""
Al cambiar a alguien de franja con las partidas hechas (#251, PR 4; D3 del 9 oct 2026).

| Caso                                        | Resultado                               |
|---------------------------------------------|-----------------------------------------|
| El organizador lo cambia de mañana a tarde  | Sale de su partida de la mañana         |
|                                             | y en la tarde queda sin partida         |
"""

import pytest

from src.modules.competition.application.use_cases.partidas_use_case import VerPartidasUseCase
from src.modules.competition.application.use_cases.plazas_en_franjas_use_case import (
    CogerPlazaUseCase,
)
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio


async def test_out_of_the_old_group_and_without_group_in_the_new_window():
    escenario = _Escenario()
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(h) for h in ("4.0", "3.0", "2.0")]
    for h in ("6.0", "5.0"):
        await escenario.con_plaza(h, franja=escenario.tarde)
    await escenario.generar()
    await escenario.generar(franja=escenario.tarde)
    quien = jugadores[0]

    await CogerPlazaUseCase(escenario.uow).execute(
        escenario.tarde.id, quien, escenario.creador, en_lugar_de=escenario.manana.id
    )

    ver = VerPartidasUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    )
    manana = await ver.execute(escenario.manana.id.value)
    tarde = await ver.execute(escenario.tarde.id.value)
    assert quien.value not in {p.user_id for g in manana.groups for p in g.players}
    assert len(manana.groups[0].players) == 2
    assert tarde.unassigned_player_ids == [quien.value]
    assert quien.value not in {p.user_id for g in tarde.groups for p in g.players}
