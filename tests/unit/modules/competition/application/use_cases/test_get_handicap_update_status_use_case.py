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

Y la misma lista que el aviso al organizador, «{N} jugadores sin actualizar con
la RFEG» (15 nov 2026), en `not_updated_players`: la ficha se abre desde ese
aviso y tiene que nombrar a los mismos. `pending_players` no cambia (es lo que
lee el front que ya está en producción y lo que el botón vuelve a preguntar).

| Caso | Situación                                                   | not_updated_players  |
|------|-------------------------------------------------------------|----------------------|
| N1   | Completa, la RFEG no encontró a un español                  | Él, con su nombre    |
| N2   | Completa, todos actualizados                                | Vacía                |
| N3   | Incompleta, falló un español y a un extranjero (fuera de     | Solo el español      |
|      | España) no se le preguntó                                   |                      |
| N4   | En España, un extranjero no encontrado                      | Él                   |
| N5   | Con hándicap personalizado                                  | No sale              |
| N6   | La primera pasada todavía en curso                          | Vacía                |
| N7   | Una incompleta que se vuelve a pasar                        | Lo de antes          |
| N8   | Cortada                                                     | Vacía                |
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.modules.competition.application.dto.competition_dto import CreateCompetitionRequestDTO
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_handicap_update_status_use_case import (
    GetHandicapUpdateStatusUseCase,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    OrigenActualizacion,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
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
    set_competition_status,
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


class _Usuarios:
    """Usuarios con nacionalidad y nombre, que es lo que mira el aviso."""

    def __init__(self):
        self.por_id: dict[UserId, MagicMock] = {}

    def alta(self, pais: str | None, nombre: str) -> UserId:
        user_id = UserId.generate()
        usuario = MagicMock()
        usuario.id = user_id
        usuario.country_code = None if pais is None else MagicMock(value=pais)
        usuario.display_name_or_legal.return_value = nombre
        self.por_id[user_id] = usuario
        return user_id

    async def find_by_ids(self, user_ids):
        return [self.por_id[u] for u in user_ids if u in self.por_id]

    async def find_by_id(self, user_id):
        return self.por_id.get(user_id)


class _ComoElAviso:
    """Una competición cerrada, en un país, con inscritos de varias nacionalidades."""

    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.usuarios = _Usuarios()
        self.organizador = self.usuarios.alta("ES", "Org")

    async def torneo(self, pais: str = "ES") -> None:
        creada = await CreateCompetitionUseCase(
            self.uow, LocationBuilder(self.uow.countries), USUARIOS_CON_GENERO
        ).execute(
            CreateCompetitionRequestDTO(
                name="Test Cup",
                start_date=date(2030, 10, 12),
                end_date=date(2030, 10, 12),
                main_country=pais,
                play_mode="SCRATCH",
                max_players=24,
            ),
            self.organizador,
        )
        await set_competition_status(self.uow, creada.id, "CLOSED")
        self.competicion = CompetitionId(creada.id)

    async def inscrito(self, pais: str | None = "ES", nombre="Luis", personalizado=False):
        user_id = self.usuarios.alta(pais, nombre)
        await create_approved_enrollment(
            self.uow, self.competicion.value, user_id, Decimal("9.0") if personalizado else None
        )
        return user_id

    async def actualizacion(self, resultados: dict, como: str = "COMPLETA"):
        """El organizador, actualizado; los demás, lo que se diga."""
        actualizacion = ActualizacionDeHandicaps.crear(
            self.competicion, OrigenActualizacion.CIERRE, AHORA
        )
        async with self.uow:
            await self.uow.handicap_updates.add(actualizacion)
            await self.uow.handicap_updates.apuntar(
                actualizacion.id, self.organizador, ResultadoRefresco.ACTUALIZADO, AHORA
            )
            for user_id, resultado in resultados.items():
                await self.uow.handicap_updates.apuntar(actualizacion.id, user_id, resultado, AHORA)
            if como == "COMPLETA":
                actualizacion.terminar(pendientes=0, momento=AHORA)
            elif como == "INCOMPLETA":
                actualizacion.terminar(pendientes=1, momento=AHORA)
            elif como == "REANUDADA":
                actualizacion.terminar(pendientes=1, momento=AHORA)
                actualizacion.reanudar(AHORA + timedelta(hours=1))
            elif como == "CORTADA":
                actualizacion.cortar(AHORA)
            await self.uow.handicap_updates.update(actualizacion)

    async def mirar(self):
        return await GetHandicapUpdateStatusUseCase(self.uow, self.usuarios).execute(
            self.competicion, self.organizador
        )


@pytest.fixture
def a():
    return _ComoElAviso()


def _ids(jugadores):
    return [p.user_id for p in jugadores]


class TestLaMismaListaQueElAviso:
    async def test_n1_completa_con_un_espanol_no_encontrado_lo_nombra(self, a):
        # Given: una completa en la que la RFEG no encontró a un español
        await a.torneo("ES")
        perdido = await a.inscrito("ES", nombre="Ana Alba")
        bien = await a.inscrito("ES")
        await a.actualizacion(
            {perdido: ResultadoRefresco.NO_ENCONTRADO, bien: ResultadoRefresco.ACTUALIZADO}
        )

        # When: el organizador mira la ficha
        resultado = await a.mirar()

        # Then: sale él, con su nombre; los pendientes de reintentar, como antes
        assert resultado.status == "COMPLETED"
        assert _ids(resultado.not_updated_players) == [perdido.value]
        assert [p.name for p in resultado.not_updated_players] == ["Ana Alba"]
        assert resultado.pending_players == []

    async def test_n2_completa_con_todos_actualizados_vacia(self, a):
        # Given
        await a.torneo("ES")
        bien = await a.inscrito("ES")
        await a.actualizacion({bien: ResultadoRefresco.ACTUALIZADO})

        # When
        resultado = await a.mirar()

        # Then
        assert resultado.not_updated_players == []

    async def test_n3_incompleta_fuera_de_espana_solo_los_espanoles(self, a):
        # Given: en Francia, un español con la RFEG caída y un francés sin preguntar
        await a.torneo("FR")
        espanol = await a.inscrito("ES")
        frances = await a.inscrito("FR")
        await a.actualizacion({espanol: ResultadoRefresco.FALLIDO}, como="INCOMPLETA")

        # When
        resultado = await a.mirar()

        # Then: el aviso nombra solo al español; los pendientes siguen siendo los dos
        assert _ids(resultado.not_updated_players) == [espanol.value]
        assert _ids(resultado.pending_players) == [espanol.value, frances.value]

    async def test_n4_en_espana_tambien_el_extranjero(self, a):
        # Given
        await a.torneo("ES")
        frances = await a.inscrito("FR")
        await a.actualizacion({frances: ResultadoRefresco.NO_ENCONTRADO})

        # When
        resultado = await a.mirar()

        # Then
        assert _ids(resultado.not_updated_players) == [frances.value]

    async def test_n5_con_handicap_personalizado_no_sale(self, a):
        # Given
        await a.torneo("ES")
        await a.inscrito("ES", personalizado=True)
        await a.actualizacion({}, como="INCOMPLETA")

        # When
        resultado = await a.mirar()

        # Then
        assert resultado.not_updated_players == []

    async def test_n6_la_primera_pasada_en_curso_vacia(self, a):
        # Given: todavía preguntando, y a uno no le ha llegado el turno
        await a.torneo("ES")
        falta = await a.inscrito("ES")
        await a.actualizacion({}, como="EN_CURSO")

        # When
        resultado = await a.mirar()

        # Then: el aviso aún no dice nada; quién falta sigue en pending_players
        assert resultado.status == "IN_PROGRESS"
        assert resultado.not_updated_players == []
        assert _ids(resultado.pending_players) == [falta.value]

    async def test_n7_una_incompleta_que_se_vuelve_a_pasar_lo_de_antes(self, a):
        # Given
        await a.torneo("ES")
        roto = await a.inscrito("ES")
        await a.actualizacion({roto: ResultadoRefresco.FALLIDO}, como="REANUDADA")

        # When
        resultado = await a.mirar()

        # Then
        assert resultado.status == "IN_PROGRESS"
        assert _ids(resultado.not_updated_players) == [roto.value]

    async def test_n8_cortada_vacia(self, a):
        # Given
        await a.torneo("ES")
        perdido = await a.inscrito("ES")
        await a.actualizacion({perdido: ResultadoRefresco.NO_ENCONTRADO}, como="CORTADA")

        # When
        resultado = await a.mirar()

        # Then
        assert resultado.status == "STOPPED"
        assert resultado.not_updated_players == []
