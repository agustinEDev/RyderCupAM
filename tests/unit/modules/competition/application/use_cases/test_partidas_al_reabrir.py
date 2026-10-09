"""
Al reabrir las inscripciones se borran las partidas (#251, PR 4; D1 del 9 oct 2026).

Pueden entrar y salir jugadores: las partidas dejarían de cuadrar. Se vuelven a
generar al cerrar.
"""

import pytest

from src.modules.competition.application.dto.competition_dto import (
    ReopenEnrollmentsRequestDTO,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio


async def test_reopening_deletes_the_groups_of_every_window():
    escenario = _Escenario()
    await escenario.guardar()
    for h in ("2.0", "1.0"):
        await escenario.con_plaza(h)
    for h in ("4.0", "3.0"):
        await escenario.con_plaza(h, franja=escenario.tarde)
    await escenario.generar()
    await escenario.generar(franja=escenario.tarde)

    await ReopenEnrollmentsUseCase(escenario.uow).execute(
        ReopenEnrollmentsRequestDTO(competition_id=escenario.competicion.id.value),
        escenario.creador,
    )

    assert await escenario.uow.partidas.de_la_competicion(escenario.competicion.id) == []
