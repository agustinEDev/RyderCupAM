"""
El estado de la actualización de hándicaps en la ficha de la competición (#251).

Si una actualización con la RFEG deja a alguien sin actualizar, se avisa al
organizador también en la competición (decidido el 7 oct 2026).

| Quién mira / qué hay            | Respuesta                                   |
|---------------------------------|---------------------------------------------|
| Un jugador                      | Nada                                        |
| Sin ninguna actualización       | Nada                                        |
| El organizador, en curso        | Estado y quién falta todavía                |
| El organizador, incompleta      | Estado y quién se quedó sin actualizar      |
| El organizador, completa        | Estado, sin pendientes                      |
| El organizador, cortada         | Estado, sin pendientes (ya no se puede)     |
| Un administrador                | Como el organizador                         |
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.modules.competition.application.use_cases.get_handicap_update_status_use_case import (
    GetHandicapUpdateStatusUseCase,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    OrigenActualizacion,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    create_approved_enrollment,
    create_competition,
)

pytestmark = pytest.mark.asyncio

AHORA = datetime(2030, 10, 10, 18, 0, tzinfo=UTC)


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.creador = UserId.generate()

    async def montar(self, estado=None, con_personalizado=False):
        respuesta = await create_competition(self.uow, self.creador)
        self.torneo = CompetitionId(respuesta.id)
        self.roto = UserId.generate()
        self.bien = UserId.generate()
        await create_approved_enrollment(self.uow, respuesta.id, self.roto)
        await create_approved_enrollment(self.uow, respuesta.id, self.bien)
        if con_personalizado:
            await create_approved_enrollment(
                self.uow, respuesta.id, UserId.generate(), Decimal("9.0")
            )
        self.actualizacion = ActualizacionDeHandicaps.crear(
            self.torneo, OrigenActualizacion.CIERRE, AHORA
        )
        async with self.uow:
            await self.uow.handicap_updates.add(self.actualizacion)
            for u in (self.creador, self.bien):
                await self.uow.handicap_updates.apuntar(
                    self.actualizacion.id, u, ResultadoRefresco.ACTUALIZADO, AHORA
                )
            await self.uow.handicap_updates.apuntar(
                self.actualizacion.id, self.roto, ResultadoRefresco.FALLIDO, AHORA
            )
            if estado == "INCOMPLETA":
                self.actualizacion.terminar(pendientes=1, momento=AHORA)
            elif estado == "COMPLETA":
                self.actualizacion.terminar(pendientes=0, momento=AHORA)
            elif estado == "CORTADA":
                self.actualizacion.cortar(AHORA)
            await self.uow.handicap_updates.update(self.actualizacion)

    async def mirar(self, quien=None, is_admin=False):
        return await GetHandicapUpdateStatusUseCase(self.uow, USUARIOS_CON_GENERO).execute(
            self.torneo, quien or self.creador, is_admin=is_admin
        )


@pytest.fixture
def e():
    return _Escenario()


class TestQuienLoVe:
    async def test_un_jugador_no_ve_nada(self, e):
        await e.montar("INCOMPLETA")

        assert await e.mirar(quien=e.bien) is None

    async def test_sin_ninguna_actualizacion_nada(self, e):
        respuesta = await create_competition(e.uow, e.creador)

        resultado = await GetHandicapUpdateStatusUseCase(e.uow, USUARIOS_CON_GENERO).execute(
            CompetitionId(respuesta.id), e.creador
        )

        assert resultado is None

    async def test_un_administrador_lo_ve(self, e):
        await e.montar("INCOMPLETA")

        resultado = await e.mirar(quien=UserId.generate(), is_admin=True)

        assert resultado is not None


class TestQueVe:
    async def test_incompleta_dice_quien_se_quedo_sin_actualizar(self, e):
        await e.montar("INCOMPLETA", con_personalizado=True)

        resultado = await e.mirar()

        assert resultado.status == "INCOMPLETE"
        assert resultado.origin == "ENROLLMENTS_CLOSED"
        assert [p.user_id for p in resultado.pending_players] == [e.roto.value]

    async def test_en_curso_dice_quien_falta_todavia(self, e):
        await e.montar()

        resultado = await e.mirar()

        assert resultado.status == "IN_PROGRESS"
        assert [p.user_id for p in resultado.pending_players] == [e.roto.value]

    @pytest.mark.parametrize("estado,valor", [("COMPLETA", "COMPLETED"), ("CORTADA", "STOPPED")])
    async def test_completa_o_cortada_sin_pendientes(self, e, estado, valor):
        await e.montar(estado)

        resultado = await e.mirar()

        assert resultado.status == valor
        assert resultado.pending_players == []
        assert resultado.finished_at == AHORA
