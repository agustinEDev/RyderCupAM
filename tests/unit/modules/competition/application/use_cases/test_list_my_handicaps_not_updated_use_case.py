"""
«Requiere tu Atención»: los hándicaps sin actualizar con la RFEG (15 nov 2026).

Lo que el panel enseña a quien pregunta, como organizador y como jugador. Se
calcula al vuelo con la última actualización de cada competición: no hay nada
que borrar cuando deja de ser cierto.

| Caso | Situación                                                  | Organizador        | Jugador    |
|------|------------------------------------------------------------|--------------------|------------|
| H2   | Cerrada, terminada, un español no encontrado               | 1, con su nombre   | Sí (H3)    |
| H4   | Cerrada, la RFEG falló con un español                      | 1                  | No         |
| H6   | Extranjero en una competición en España                    | 1                  | No         |
| H6   | Extranjero en una competición fuera de España              | Nada               | No         |
| H1   | La primera pasada todavía en curso                         | Nada               | No         |
| H1   | Una incompleta que se vuelve a pasar                       | Lo de antes        | Lo de antes|
| H5   | La RFEG lo encuentra después (perfil u otra pasada)        | Nada               | No         |
| D1   | Se pone el hándicap a mano                                 | Sigue              | Sigue      |
| T4   | Aprobado después de una COMPLETA (nunca preguntado)        | Nada               | No         |
| T2   | Organiza muchas: solo se leen las cerradas (por la base)   | —                  | —          |
| T2   | Organiza y juega: cada competición se mira una vez         | —                  | —          |
| T2   | Como jugador se lee solo su resultado                      | —                  | —          |
| R10  | Su usuario no se puede leer a mitad                        | —                  | Lo ya visto se queda |
| H5   | La competición empieza                                     | Nada               | No         |
| H5   | Nadie queda sin actualizar                                 | Nada               | —          |
| —    | Solo cuenta la última actualización                        | La última          | La última  |
| —    | Otro usuario (ni organiza ni está inscrito)                | Nada               | No         |
| —    | Un jugador ve lo suyo, no la lista de otros                | —                  | Solo él    |
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.modules.competition.application.dto.competition_dto import CreateCompetitionRequestDTO
from src.modules.competition.application.services.sin_actualizar_de_la_competicion import (
    SinActualizarDeLaCompeticion,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_my_handicaps_not_updated_use_case import (
    ListMyHandicapsNotUpdatedUseCase,
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
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    create_approved_enrollment,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio

CREADA = datetime(2030, 10, 10, 18, 0, tzinfo=UTC)
CONTESTO = CREADA + timedelta(minutes=1)


class _Usuarios:
    """Los usuarios con lo que se mira: país, cuándo se actualizó y nombre."""

    def __init__(self):
        self.por_id: dict[UserId, MagicMock] = {}

    def alta(self, pais: str | None = "ES", nombre: str = "Jugador") -> UserId:
        user_id = UserId.generate()
        usuario = MagicMock()
        usuario.id = user_id
        usuario.country_code = None if pais is None else MagicMock(value=pais)
        usuario.handicap_updated_at = None
        usuario.display_name_or_legal.return_value = nombre
        self.por_id[user_id] = usuario
        return user_id

    async def find_by_ids(self, user_ids):
        return [self.por_id[u] for u in user_ids if u in self.por_id]

    async def find_by_id(self, user_id):
        return self.por_id.get(user_id)


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.usuarios = _Usuarios()
        self.organizador = self.usuarios.alta(nombre="Org")
        self._creadas = 0

    async def torneo(self, pais: str = "ES") -> CompetitionId:
        """Una competición cerrada de este organizador, en ese país."""
        self._creadas += 1
        creada = await CreateCompetitionUseCase(
            self.uow, LocationBuilder(self.uow.countries), USUARIOS_CON_GENERO
        ).execute(
            CreateCompetitionRequestDTO(
                name="Test Cup" if self._creadas == 1 else f"Test Cup {self._creadas}",
                start_date=date(2030, 10, 12),
                end_date=date(2030, 10, 12),
                main_country=pais,
                play_mode="SCRATCH",
                max_players=24,
            ),
            self.organizador,
        )
        await set_competition_status(self.uow, creada.id, "CLOSED")
        return CompetitionId(creada.id)

    async def inscrito(self, torneo, pais: str | None = "ES", nombre="Luis") -> UserId:
        user_id = self.usuarios.alta(pais, nombre)
        await create_approved_enrollment(self.uow, torneo.value, user_id)
        return user_id

    async def actualizacion(
        self, torneo, resultados: dict, terminar=True, creada=CREADA
    ) -> ActualizacionDeHandicaps:
        """Una actualización con esos resultados; terminada, completa o incompleta."""
        actualizacion = ActualizacionDeHandicaps.crear(torneo, OrigenActualizacion.CIERRE, creada)
        async with self.uow:
            await self.uow.handicap_updates.add(actualizacion)
            # El organizador, actualizado si no se dice otra cosa de él
            if self.organizador not in resultados:
                await self.uow.handicap_updates.apuntar(
                    actualizacion.id, self.organizador, ResultadoRefresco.ACTUALIZADO, CONTESTO
                )
            for user_id, resultado in resultados.items():
                await self.uow.handicap_updates.apuntar(
                    actualizacion.id, user_id, resultado, CONTESTO
                )
            if terminar:
                fallidos = sum(r is ResultadoRefresco.FALLIDO for r in resultados.values())
                actualizacion.terminar(fallidos, CONTESTO)
                await self.uow.handicap_updates.update(actualizacion)
        return actualizacion

    async def empezar(self, torneo) -> None:
        async with self.uow:
            competicion = await self.uow.competitions.find_by_id(torneo)
            competicion.start()
            await self.uow.competitions.update(competicion)

    async def la_rfeg_lo_encuentra(self, torneo, user_id) -> None:
        """Lo pidió desde su perfil y la RFEG lo encontró: queda apuntado (D1)."""
        ultima = await self.uow.handicap_updates.ultima_de(torneo)
        await self.uow.handicap_updates.apuntar(
            ultima.id, user_id, ResultadoRefresco.ACTUALIZADO, CONTESTO + timedelta(hours=1)
        )

    async def ver(self, quien: UserId):
        return await ListMyHandicapsNotUpdatedUseCase(self.uow, self.usuarios).execute(quien)


@pytest.fixture
def e() -> _Escenario:
    return _Escenario()


def _ids(items) -> list[UUID]:
    return [i.competition_id for i in items]


class TestOrganizador:
    async def test_un_espanol_no_encontrado(self, e):
        """
        Given una competición cerrada con un español al que la RFEG no encontró
        When el organizador mira «Requiere tu Atención»
        Then le sale la competición con 1 y su nombre (H2)
        """
        torneo = await e.torneo()
        luis = await e.inscrito(torneo, nombre="Luis Pérez")
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})

        visto = await e.ver(e.organizador)

        [item] = visto.as_organizer
        assert item.competition_id == torneo.value
        assert item.competition_name == "Test Cup"
        assert item.count == 1
        assert [(p.user_id, p.name) for p in item.players] == [(luis.value, "Luis Pérez")]
        assert visto.as_player == []

    async def test_la_rfeg_fallo(self, e):
        """Given la RFEG falló con un español When mira Then le sale (H4)."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.FALLIDO})

        assert [i.count for i in (await e.ver(e.organizador)).as_organizer] == [1]

    async def test_extranjero_en_espana_si_y_fuera_no(self, e):
        """
        Given un extranjero en una competición en España y otro en una de Francia
        When el organizador mira
        Then le sale solo la de España (H2, H6)
        """
        en_espana, en_francia = await e.torneo("ES"), await e.torneo("FR")
        for torneo in (en_espana, en_francia):
            fuera = await e.inscrito(torneo, pais="FR")
            await e.actualizacion(torneo, {fuera: ResultadoRefresco.SIN_LICENCIA_ESPANOLA})

        assert _ids((await e.ver(e.organizador)).as_organizer) == [en_espana.value]

    async def test_sin_nacionalidad_cuenta_como_extranjero(self, e):
        """Given uno sin nacionalidad, fuera de España When mira Then no sale."""
        torneo = await e.torneo("FR")
        nadie = await e.inscrito(torneo, pais=None)
        await e.actualizacion(torneo, {nadie: ResultadoRefresco.SIN_LICENCIA_ESPANOLA})

        assert (await e.ver(e.organizador)).as_organizer == []

    async def test_nadie_sin_actualizar_no_sale(self, e):
        """Given todos actualizados When mira Then no sale nada (H5)."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.ACTUALIZADO})

        assert (await e.ver(e.organizador)).as_organizer == []

    async def test_la_primera_pasada_en_curso_no_sale(self, e):
        """Given la del cierre todavía preguntando When mira Then nada aún (H1)."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO}, terminar=False)

        assert (await e.ver(e.organizador)).as_organizer == []

    async def test_una_incompleta_que_se_vuelve_a_pasar_sigue_saliendo(self, e):
        """
        Given una incompleta que se vuelve a pasar
        When mira mientras corre
        Then sigue saliendo lo de antes (H1)
        """
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        actualizacion = await e.actualizacion(torneo, {luis: ResultadoRefresco.FALLIDO})
        actualizacion.reanudar(CONTESTO + timedelta(hours=1))
        async with e.uow:
            await e.uow.handicap_updates.update(actualizacion)

        assert [i.count for i in (await e.ver(e.organizador)).as_organizer] == [1]

    async def test_al_empezar_desaparece(self, e):
        """Given uno no encontrado When la competición empieza Then ya no sale (H5)."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        await e.empezar(torneo)

        visto = await e.ver(e.organizador)

        assert visto.as_organizer == []

    async def test_si_lo_actualiza_desaparece(self, e):
        """
        Given uno no encontrado
        When actualiza su hándicap después (desde su perfil)
        Then ya no sale para el organizador (H5)
        """
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        await e.la_rfeg_lo_encuentra(torneo, luis)

        assert (await e.ver(e.organizador)).as_organizer == []

    async def test_solo_cuenta_la_ultima(self, e):
        """Given una vieja con un no encontrado y otra nueva sin nadie When mira Then nada."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        await e.actualizacion(
            torneo, {luis: ResultadoRefresco.ACTUALIZADO}, creada=CREADA + timedelta(days=1)
        )

        assert (await e.ver(e.organizador)).as_organizer == []

    async def test_otro_usuario_no_ve_nada(self, e):
        """Given una con un no encontrado When mira alguien ajeno Then no ve nada."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})

        visto = await e.ver(e.usuarios.alta())

        assert visto.as_organizer == []
        assert visto.as_player == []

    async def test_aprobado_tras_una_completa_no_sale(self, e):
        """
        Given una actualización COMPLETA y un jugador aprobado después
        When el organizador mira
        Then no sale: nadie le preguntó porque llegó tarde (T4)
        """
        torneo = await e.torneo()
        await e.actualizacion(torneo, {})
        await e.inscrito(torneo)

        assert (await e.ver(e.organizador)).as_organizer == []

    async def test_solo_lee_sus_cerradas(self, e):
        """
        Given un organizador con competiciones
        When mira
        Then se piden a la base solo las cerradas suyas, no todas (T2)
        """
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        e.uow.competitions.find_by_creator = AsyncMock(side_effect=AssertionError("todas"))
        original = e.uow.competitions.find_by_filters
        pedidas = []

        async def find_by_filters(**kwargs):
            pedidas.append(kwargs)
            return await original(**kwargs)

        e.uow.competitions.find_by_filters = find_by_filters

        assert _ids((await e.ver(e.organizador)).as_organizer) == [torneo.value]
        assert [(p["creator_id"], p["status"]) for p in pedidas] == [
            (e.organizador, CompetitionStatus.CLOSED)
        ]

    async def test_organiza_y_juega_se_mira_una_vez(self, e, monkeypatch):
        """
        Given un organizador que también juega y no fue encontrado
        When mira
        Then le sale en las dos listas y la competición se calcula una sola vez (T2)
        """
        torneo = await e.torneo()
        await e.actualizacion(torneo, {e.organizador: ResultadoRefresco.NO_ENCONTRADO})
        calculos = []
        original = SinActualizarDeLaCompeticion.de

        async def contado(*args):
            calculos.append(args[2].id)
            return await original(*args)

        monkeypatch.setattr(SinActualizarDeLaCompeticion, "de", staticmethod(contado))
        monkeypatch.setattr(
            SinActualizarDeLaCompeticion,
            "no_encontrado",
            staticmethod(AsyncMock(side_effect=AssertionError("otra vez"))),
        )

        visto = await e.ver(e.organizador)

        assert _ids(visto.as_organizer) == [torneo.value]
        assert _ids(visto.as_player) == [torneo.value]
        assert calculos == [torneo]

    async def test_si_su_usuario_no_se_lee_no_pierde_lo_ya_visto(self, e):
        """
        Given un organizador no encontrado en la suya y apuntado en otra
        When su usuario no se puede leer al mirar la otra
        Then conserva la suya en su lista de jugador (R10)
        """
        suya = await e.torneo()
        await e.actualizacion(suya, {e.organizador: ResultadoRefresco.NO_ENCONTRADO})
        otro = _Escenario()
        otro.uow, otro.usuarios, otro._creadas = e.uow, e.usuarios, 1
        otro.organizador = e.usuarios.alta(nombre="Otro")
        ajena = await otro.torneo()
        await create_approved_enrollment(e.uow, ajena.value, e.organizador)
        await otro.actualizacion(ajena, {e.organizador: ResultadoRefresco.NO_ENCONTRADO})
        e.usuarios.find_by_id = AsyncMock(return_value=None)

        visto = await e.ver(e.organizador)

        assert _ids(visto.as_player) == [suya.value]


class TestJugador:
    async def test_el_espanol_no_encontrado_ve_la_suya(self, e):
        """
        Given un español no encontrado
        When mira su panel
        Then le sale la competición, y no la lista del organizador (H3)
        """
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        otro = await e.inscrito(torneo)
        await e.actualizacion(
            torneo, {luis: ResultadoRefresco.NO_ENCONTRADO, otro: ResultadoRefresco.FALLIDO}
        )

        visto = await e.ver(luis)

        [item] = visto.as_player
        assert item.competition_id == torneo.value
        assert item.competition_name == "Test Cup"
        assert visto.as_organizer == []

    async def test_si_la_rfeg_fallo_no_le_sale(self, e):
        """Given la RFEG falló con él When mira Then no le sale nada (H4)."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.FALLIDO})

        assert (await e.ver(luis)).as_player == []

    async def test_un_extranjero_nunca(self, e):
        """Given un extranjero apuntado como no encontrado When mira Then nada (H6)."""
        torneo = await e.torneo()
        fuera = await e.inscrito(torneo, pais="PT")
        await e.actualizacion(torneo, {fuera: ResultadoRefresco.NO_ENCONTRADO})

        assert (await e.ver(fuera)).as_player == []

    async def test_si_lo_actualiza_desaparece(self, e):
        """Given no encontrado When lo pide desde su perfil y lo encuentra Then desaparece (H5)."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        await e.la_rfeg_lo_encuentra(torneo, luis)

        assert (await e.ver(luis)).as_player == []

    async def test_a_mano_no_cuenta(self, e):
        """
        Given un no encontrado
        When se pone el hándicap a mano (él o un administrador)
        Then le sigue saliendo a él y al organizador: solo cuenta la RFEG (D1)
        """
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        e.usuarios.por_id[luis].handicap_updated_at = CONTESTO + timedelta(days=1)

        assert _ids((await e.ver(luis)).as_player) == [torneo.value]
        assert _ids((await e.ver(e.organizador)).as_organizer) == [torneo.value]

    async def test_lee_solo_su_resultado(self, e):
        """
        Given un no encontrado en una competición que no organiza
        When mira
        Then se lee solo su resultado, no los de todos (T2)
        """
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        e.uow.handicap_updates.resultados = AsyncMock(side_effect=AssertionError("todos"))

        assert _ids((await e.ver(luis)).as_player) == [torneo.value]

    async def test_si_se_retiro_no_le_sale(self, e):
        """Given no encontrado When se retira de la competición Then ya no le sale."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        async with e.uow:
            [inscripcion] = await e.uow.enrollments.find_by_user_ids_and_competition([luis], torneo)
            inscripcion.withdraw()
            await e.uow.enrollments.update(inscripcion)

        assert (await e.ver(luis)).as_player == []

    async def test_al_empezar_desaparece(self, e):
        """Given no encontrado When la competición empieza Then desaparece (H5)."""
        torneo = await e.torneo()
        luis = await e.inscrito(torneo)
        await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})
        await e.empezar(torneo)

        assert (await e.ver(luis)).as_player == []

    async def test_en_varias_competiciones_ve_cada_una(self, e):
        """Given no encontrado en dos competiciones When mira Then le salen las dos."""
        primera, segunda = await e.torneo(), await e.torneo()
        luis = e.usuarios.alta()
        for torneo in (primera, segunda):
            await create_approved_enrollment(e.uow, torneo.value, luis)
            await e.actualizacion(torneo, {luis: ResultadoRefresco.NO_ENCONTRADO})

        assert sorted(_ids((await e.ver(luis)).as_player)) == sorted([primera.value, segunda.value])
