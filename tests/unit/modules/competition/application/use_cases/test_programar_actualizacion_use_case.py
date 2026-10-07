"""
Programar la actualización de hándicaps (#251, decidido el 7 oct 2026).

Una pendiente por competición, que se puede cambiar o anular hasta su hora. Se
programa dentro de la ventana del botón, mirada en la hora elegida.

| Caso                                              | Resultado                          |
|---------------------------------------------------|------------------------------------|
| A una hora dentro de la ventana                   | Programada                         |
| Programar otra vez                                | Sustituye a la anterior            |
| A una hora pasada                                 | 400                                |
| A una hora fuera de la ventana (pegada a salida)  | 400 con el motivo                  |
| Un jugador                                        | 403                                |
| Sin el refresco encendido                         | 409                                |
| Anular                                            | Ya no hay ninguna                  |
| La ficha                                          | Dice para cuándo está programada   |
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    ActualizacionNoPermitidaError,
    NotCompetitionCreatorError,
    RefrescoDesactivadoError,
)
from src.modules.competition.application.use_cases.actualizar_handicaps_use_case import (
    VentanaDeActualizacionUseCase,
)
from src.modules.competition.application.use_cases.programar_actualizacion_use_case import (
    AnularProgramacionUseCase,
    ProgramarActualizacionUseCase,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_actualizar_handicaps_use_case import (  # noqa: F401
    A_TIEMPO,
    CERCA,
    _Escenario,
    e,
)

pytestmark = pytest.mark.asyncio

A_LAS_TRES = datetime(2030, 10, 11, 1, 0, tzinfo=UTC)  # 3:00 en Madrid


def _programar(e, para, quien=None, refresco_activo=True):  # noqa: F811
    return ProgramarActualizacionUseCase(
        e.uow, e.zonas, reloj=lambda: A_TIEMPO, refresco_activo=refresco_activo
    ).execute(e.competicion.id, quien or e.creador, para)


class TestProgramar:
    async def test_dentro_de_la_ventana(self, e):  # noqa: F811
        await e.torneo()

        await _programar(e, A_LAS_TRES)

        assert await e.uow.handicap_updates.programada_de(e.competicion.id) == A_LAS_TRES

    async def test_otra_vez_sustituye(self, e):  # noqa: F811
        await e.torneo()
        await _programar(e, A_LAS_TRES)

        await _programar(e, datetime(2030, 10, 11, 2, 0, tzinfo=UTC))

        assert await e.uow.handicap_updates.programada_de(e.competicion.id) == datetime(
            2030, 10, 11, 2, 0, tzinfo=UTC
        )

    async def test_a_una_hora_pasada_no(self, e):  # noqa: F811
        await e.torneo()

        with pytest.raises(ActualizacionNoPermitidaError, match="futuro"):
            await _programar(e, datetime(2030, 10, 10, 17, 0, tzinfo=UTC))

    async def test_justo_ahora_tampoco(self, e):  # noqa: F811
        await e.torneo()

        with pytest.raises(ActualizacionNoPermitidaError, match="futuro"):
            await _programar(e, A_TIEMPO)

    async def test_fuera_de_la_ventana_no(self, e):  # noqa: F811
        await e.torneo()

        with pytest.raises(ActualizacionNoPermitidaError, match="salida"):
            await _programar(e, CERCA)

    async def test_pegada_al_cierre_tampoco(self, e):  # noqa: F811
        """El vigilante pasa cada minuto: hace falta margen para que llegue a tiempo."""
        await e.torneo()
        # La ventana cierra a las 6:59 UTC (9:00 en Madrid menos 6 x 10 s)
        un_minuto_antes = datetime(2030, 10, 11, 6, 58, tzinfo=UTC)

        with pytest.raises(ActualizacionNoPermitidaError, match="margen"):
            await _programar(e, un_minuto_antes)

    async def test_un_jugador_no(self, e):  # noqa: F811
        await e.torneo()

        with pytest.raises(NotCompetitionCreatorError):
            await _programar(e, A_LAS_TRES, quien=UserId(uuid4()))

    async def test_sin_el_refresco_encendido_no(self, e):  # noqa: F811
        await e.torneo()

        with pytest.raises(RefrescoDesactivadoError):
            await _programar(e, A_LAS_TRES, refresco_activo=False)


class TestAnularYVer:
    async def test_anular(self, e):  # noqa: F811
        await e.torneo()
        await _programar(e, A_LAS_TRES)

        await AnularProgramacionUseCase(e.uow).execute(e.competicion.id, e.creador)

        assert await e.uow.handicap_updates.programada_de(e.competicion.id) is None

    async def test_anular_un_jugador_no(self, e):  # noqa: F811
        await e.torneo()

        with pytest.raises(NotCompetitionCreatorError):
            await AnularProgramacionUseCase(e.uow).execute(e.competicion.id, UserId(uuid4()))

    async def test_la_ficha_dice_para_cuando(self, e):  # noqa: F811
        await e.torneo()
        await _programar(e, A_LAS_TRES)

        ventana = await VentanaDeActualizacionUseCase(e.uow, e.zonas, lambda: A_TIEMPO).execute(
            e.competicion.id, e.creador
        )

        assert ventana.scheduled_at == A_LAS_TRES
