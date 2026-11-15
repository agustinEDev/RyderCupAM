"""
Una actualización de hándicaps con la RFEG, de punta a punta (#251, 7 oct 2026).

Al cerrar las inscripciones se crea una actualización y se lanza en segundo
plano. La pasada pregunta a la RFEG por cada inscrito sin hándicap
personalizado, uno a uno y con pausa, con hasta 3 intentos por jugador, y
apunta qué pasó. En un Stableford o un Medal todavía cerrado, si la RFEG da
otro hándicap, se corrige el fijado y se rehacen las categorías; en la Ryder
solo cambia el perfil. Si alguien se queda sin actualizar, queda incompleta y
se avisa al organizador por correo.

| Caso                                              | Resultado                                |
|---------------------------------------------------|------------------------------------------|
| Al cerrar desde abierta                           | Se crea una y se lanza tras guardar      |
| Sin lanzador (apagado fuera de producción)        | No se crea ninguna                       |
| Cerrar de nuevo                                   | La anterior a medias se corta            |
| Al iniciar                                        | La que esté a medias se corta            |
| La pasada                                         | Pregunta por cada inscrito, con pausa    |
| Con personalizado                                 | No pregunta                              |
| La RFEG falla                                     | 3 intentos con pausa, y sigue            |
| Falla las 3 veces                                 | Incompleta, y correo al organizador      |
| Todos contestan                                   | Completa, sin correo                     |
| Una a medias se vuelve a pasar                    | Solo lo que falta                        |
| Sin licencia española                             | Apunta, sin preguntar a la RFEG          |
| Stableford cerrado y la RFEG da otro              | Corrige el fijado y las categorías       |
| Personalizado en otra competición                 | Allí no se toca                          |
| La competición empieza a mitad                    | Para, y lo pendiente no se toca          |
| Se corta mientras contesta la RFEG                | No corrige el fijado                     |
| Se corta con el último jugador                    | Sin correo                               |
| Volver a cerrar desde en juego                    | No lanza otra                            |
| Nombrar capitanes con inscripciones abiertas      | También la lanza (cierra)                |
| Cambiar capitanes ya cerrada                      | No lanza otra                            |
| Al reabrir                                        | La que esté a medias se corta            |
| Se corta con un jugador fallando                  | No reintenta con él                      |
| Ryder cerrada                                     | Solo el perfil                           |
| La RFEG se consulta                               | Sin ninguna transacción abierta          |
| Un fallo inesperado                               | Se apunta como fallido, y sigue          |

Sin actualizar con la RFEG (15 nov 2026, H1-H6; al final del fichero):

| Caso | Al terminar la pasada                           | Organizador          | Jugador            |
|------|-------------------------------------------------|----------------------|--------------------|
| H1   | Todos actualizados                              | Nada                 | Nada               |
| H3   | Español no encontrado (queda completa)          | Correo y Actividad   | Correo y Actividad |
| H4   | Español con la RFEG caída (incompleta)          | Correo y Actividad   | Nada               |
| H2   | Extranjero en una competición en España         | Correo y Actividad   | Nada (H6)          |
| H6   | Extranjero en una competición fuera de España   | Nada                 | Nada               |
| H1   | Otra pasada de una incompleta                   | Otra vez, al día     | No se repite       |
| H1   | Se corta antes de acabar                        | Nada                 | Nada               |
| —    | Correo o Actividad caídos                       | No tumban la pasada  |                    |
| D2   | Otra actualización tampoco lo encuentra         | —                    | Actividad, sin correo |
| D2   | Otra pasada con la misma lista                  | Actividad, sin correo|                    |
| D2   | La lista cambia                                 | Correo otra vez      |                    |
| D2   | La lista se vacía y vuelve la misma             | Correo otra vez      |                    |
| D3   | Otra pasada deja a todos actualizados           | Se retira su aviso   | Se retira el suyo  |
| T1   | Montar Actividad falla, o al cerrarla           | La pasada acaba igual, con sus correos   |

Desde su perfil (D1 y D4, 16 nov 2026; al final del fichero): la RFEG encuentra
su hándicap fuera de una actualización.

| Caso | Competición                                     | Resultado                                |
|------|-------------------------------------------------|------------------------------------------|
| D1   | Cerrada, con una actualización                  | Queda apuntado como actualizado          |
| D4   | Stableford cerrado                              | Corrige el fijado y rehace categorías    |
| D4   | ... con su partida sin salir                    | Su hándicap de juego también             |
| D4   | Con personalizado                               | El fijado no se toca                     |
| D4   | Ya en juego                                     | Nada                                     |
| D4   | Cerrada, pero con la ventana cerrada            | Apuntado, el fijado no se toca           |
| D4   | Inscrito sin aprobar                            | Nada                                     |
| D4   | Ryder cerrada                                   | Apuntado; no hay fijado                  |
| D3   | Era el único no encontrado                      | Se retira el suyo y el del organizador   |
| D3   | Quedan otros sin actualizar                     | Se retira el suyo; el organizador, con N |
| D3   | La primera pasada aún en curso                  | Se retira el suyo; el organizador, nada  |
| T1   | Actividad falla                                 | El fijado se corrige igual               |
"""

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    CreateCompetitionRequestDTO,
    NameCaptainsRequestDTO,
    ReopenEnrollmentsRequestDTO,
    StartCompetitionRequestDTO,
    StrokePlaySettingsDTO,
)
from src.modules.competition.application.services.handicaps_al_cerrar import HandicapsAlCerrar
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.handicap_de_la_rfeg_del_perfil_use_case import (
    HandicapDeLaRfegDelPerfilUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.refrescar_handicaps_use_case import (
    PAUSA_ENTRE_INTENTOS,
    PAUSA_ENTRE_JUGADORES,
    Herramientas,
    RefrescarHandicapsUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Intento,
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    montar_calendario,
    plaza_para_todos,
)

pytestmark = pytest.mark.asyncio

AHORA = datetime(2030, 10, 10, 18, 0, tzinfo=UTC)


class _Usuarios:
    """Los jugadores, con lo que mira el refresco: país, nombre, correo y hándicap."""

    def __init__(self):
        self.por_id: dict[UserId, MagicMock] = {}
        self.save = AsyncMock()

    def alta(self, pais: str = "ES", handicap: float = 10.0) -> UserId:
        user_id = UserId.generate()
        usuario = MagicMock()
        usuario.id = user_id
        usuario.country_code = MagicMock(value=pais)
        usuario.handicap_updated_at = None
        usuario.handicap = MagicMock(value=handicap)
        usuario.gender = Gender.MALE
        usuario.email = MagicMock(value=f"{user_id}@test.com")
        usuario.get_full_name.return_value = f"Jugador {user_id}"
        usuario.display_name_or_legal.return_value = f"Jugador {user_id}"

        def actualizar(valor, usuario=usuario):
            usuario.handicap = MagicMock(value=valor)

        usuario.update_handicap.side_effect = actualizar
        self.por_id[user_id] = usuario
        return user_id

    async def find_by_ids(self, user_ids):
        return [self.por_id[u] for u in user_ids if u in self.por_id]

    async def find_by_id(self, user_id: UserId):
        return self.por_id.get(user_id)


class _UnidadQueCuenta(InMemoryUnitOfWork):
    """Sabe si hay una transacción abierta, para ver dónde se pregunta a la RFEG."""

    def __init__(self):
        super().__init__()
        self.abiertas = 0
        self.al_abrir = None

    async def __aenter__(self):
        self.abiertas += 1
        if self.al_abrir is not None:
            self.al_abrir()
        return await super().__aenter__()

    async def __aexit__(self, *args):
        self.abiertas -= 1
        return await super().__aexit__(*args)


class _Lanzador:
    """Apunta qué se lanzó, y cuántas transacciones había abiertas en ese momento."""

    def __init__(self, uow):
        self._uow = uow
        self.lanzadas: list = []
        self.abiertas_al_lanzar: list[int] = []

    def lanzar(self, update_id) -> None:
        self.lanzadas.append(update_id)
        self.abiertas_al_lanzar.append(self._uow.abiertas)


class _Madrid:
    """Todos los campos, en Madrid."""

    async def for_course(self, _campo):
        return "Europe/Madrid"

    async def for_competition(self, _competicion):
        return "Europe/Madrid"


class _Escenario:
    def __init__(self):
        self.uow = _UnidadQueCuenta()
        self.usuarios = _Usuarios()
        self.rfeg = MagicMock()
        self.rfeg.search_handicap = AsyncMock(return_value=11.2)
        self.avisos = MagicMock()
        self.avisos.send_handicaps_pending_email = AsyncMock(return_value=True)
        self.avisos.send_handicap_not_found_email = AsyncMock(return_value=True)
        self.actividad = MagicMock()
        self.actividad.handicaps_not_updated = AsyncMock()
        self.actividad.handicap_not_found = AsyncMock()
        self.actividad.handicaps_not_updated_withdrawn = AsyncMock()
        self.actividad.handicap_not_found_withdrawn = AsyncMock()
        # Montarla o cerrarla puede fallar (T1)
        self.al_montar_actividad: Exception | None = None
        self.al_cerrar_actividad: Exception | None = None
        self.actividades_montadas = 0
        self.lanzador = _Lanzador(self.uow)
        self.esperas: list[float] = []
        self.creadores: dict[CompetitionId, UserId] = {}
        self.ahora = AHORA

    async def esperar(self, segundos: float) -> None:
        self.esperas.append(segundos)

    async def torneo(
        self, tipo="RYDER_CUP", limites=("12.0",), contador=None, pais="ES"
    ) -> CompetitionId:
        """Una competición con las inscripciones abiertas; su creador, sin personalizado."""
        creador = self.usuarios.alta()
        extra = {}
        if tipo != "RYDER_CUP":
            extra["stroke_play"] = (
                StrokePlaySettingsDTO(category_count=contador)
                if contador
                else StrokePlaySettingsDTO(category_limits=[Decimal(x) for x in limites])
            )
        respuesta = await CreateCompetitionUseCase(
            self.uow, LocationBuilder(self.uow.countries), self.usuarios
        ).execute(
            CreateCompetitionRequestDTO(
                name="Medal de octubre",
                start_date=date(2030, 10, 12),
                end_date=date(2030, 10, 12),
                main_country=pais,
                play_mode="HANDICAP",
                tournament_type=tipo,
                **extra,
            ),
            creador,
        )
        torneo = CompetitionId(respuesta.id)
        self.creadores[torneo] = creador
        return torneo

    async def inscrito(self, torneo, pais="ES", personalizado=None, handicap=10.0) -> UserId:
        user_id = self.usuarios.alta(pais, handicap)
        await create_approved_enrollment(self.uow, torneo.value, user_id, personalizado)
        return user_id

    async def cerrar(self, torneo, lanzador=True) -> None:
        # Sin franja no se cierra un stroke play (#251, 8 oct 2026)
        await plaza_para_todos(self.uow, torneo)
        await CloseEnrollmentsUseCase(
            self.uow, self.usuarios, self.lanzador if lanzador else None
        ).execute(CloseEnrollmentsRequestDTO(competition_id=torneo.value), self.creadores[torneo])

    async def iniciar(self, torneo) -> None:
        await montar_calendario(self.uow, torneo.value, "sin jugar")
        await StartCompetitionUseCase(self.uow, self.usuarios).execute(
            StartCompetitionRequestDTO(competition_id=torneo.value), self.creadores[torneo]
        )

    async def franja(self, torneo, primera=time(9, 0)) -> None:
        """Una franja el día del torneo (12 oct), en Madrid."""
        async with self.uow:
            await self.uow.rounds.add(
                Round.create_franja(
                    competition_id=torneo,
                    golf_course_id=GolfCourseId.generate(),
                    round_date=date(2030, 10, 12),
                    session_type=SessionType.MORNING,
                    hoja_de_salidas=HojaDeSalidas(primera, time(12, 0), 10, 4),
                )
            )

    async def mover(self, torneo, transicion: str) -> None:
        """Una transición directa de la competición, sin casos de uso."""
        competicion = await self.uow.competitions.find_by_id(torneo)
        getattr(competicion, transicion)()
        await self.uow.competitions.update(competicion)

    @asynccontextmanager
    async def herramientas(self):
        yield Herramientas(
            competiciones=self.uow,
            usuarios=self.usuarios,
            zonas=_Madrid(),
            campos=getattr(self, "campos", None),
        )

    def caso(self) -> RefrescarHandicapsUseCase:
        return RefrescarHandicapsUseCase(
            herramientas=self.herramientas,
            handicap_service=self.rfeg,
            avisos=self.avisos,
            reloj=lambda: self.ahora,
            esperar=self.esperar,
            actividad=self.fabrica_de_actividad,
        )

    @asynccontextmanager
    async def fabrica_de_actividad(self):
        """Actividad sobre su sesión, que puede fallar al montarla o al cerrarla."""
        if self.al_montar_actividad is not None:
            raise self.al_montar_actividad
        self.actividades_montadas += 1
        yield self.actividad
        if self.al_cerrar_actividad is not None:
            raise self.al_cerrar_actividad

    async def pasar(self, torneo) -> int:
        """Una pasada de la última actualización de la competición."""
        ultima = await self.uow.handicap_updates.ultima_de(torneo)
        return await self.caso().execute(ultima.id)

    async def ultima(self, torneo):
        return await self.uow.handicap_updates.ultima_de(torneo)

    def preguntados(self) -> list[str]:
        return [llamada.args[0] for llamada in self.rfeg.search_handicap.await_args_list]

    def nombre(self, user_id: UserId) -> str:
        return f"Jugador {user_id}"

    async def apuntado(self, torneo) -> dict[UserId, Intento]:
        return await self.uow.handicap_updates.resultados((await self.ultima(torneo)).id)

    async def inscripciones(self, torneo):
        return {
            e.user_id: e
            for e in await self.uow.enrollments.find_by_competition_and_status(
                torneo, EnrollmentStatus.APPROVED
            )
        }


@pytest.fixture
def e() -> _Escenario:
    return _Escenario()


class TestAlCerrar:
    async def test_se_crea_una_y_se_lanza_despues_de_guardar(self, e):
        torneo = await e.torneo()

        await e.cerrar(torneo)

        ultima = await e.ultima(torneo)
        assert ultima.origen is OrigenActualizacion.CIERRE
        assert ultima.estado is EstadoActualizacion.EN_CURSO
        assert e.lanzador.lanzadas == [ultima.id]
        assert e.lanzador.abiertas_al_lanzar == [0]

    async def test_sin_lanzador_no_se_crea_ninguna(self, e):
        torneo = await e.torneo()

        await e.cerrar(torneo, lanzador=False)

        assert await e.ultima(torneo) is None

    async def test_cerrar_de_nuevo_corta_la_anterior_y_lanza_otra(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)
        primera = await e.ultima(torneo)
        await e.mover(torneo, "reopen_enrollments")

        await e.cerrar(torneo)

        cortada = await e.uow.handicap_updates.find_by_id(primera.id)
        assert cortada.estado is EstadoActualizacion.CORTADA
        assert len(e.lanzador.lanzadas) == 2
        assert (await e.ultima(torneo)).id == e.lanzador.lanzadas[-1] != primera.id

    async def test_volver_a_cerrar_desde_en_juego_no_lanza_otra(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)
        await e.iniciar(torneo)

        # El mismo botón de cerrar devuelve a cerrada una competición en juego
        await e.cerrar(torneo)

        assert len(e.lanzador.lanzadas) == 1

    async def test_nombrar_capitanes_con_las_inscripciones_abiertas_tambien_la_lanza(self, e):
        """Nombrar capitanes cierra las inscripciones de una Ryder por otro camino."""
        torneo = await e.torneo()
        otro = await e.inscrito(torneo)

        await NameCaptainsUseCase(e.uow, e.lanzador).execute(
            NameCaptainsRequestDTO(
                competition_id=torneo.value,
                team_a_captain_id=e.creadores[torneo].value,
                team_b_captain_id=otro.value,
            ),
            e.creadores[torneo],
        )

        ultima = await e.ultima(torneo)
        assert ultima.origen is OrigenActualizacion.CIERRE
        assert e.lanzador.lanzadas == [ultima.id]
        assert e.lanzador.abiertas_al_lanzar == [0]

    async def test_cambiar_capitanes_ya_cerrada_no_lanza_otra(self, e):
        torneo = await e.torneo()
        otro = await e.inscrito(torneo)
        await e.cerrar(torneo)

        await NameCaptainsUseCase(e.uow, e.lanzador).execute(
            NameCaptainsRequestDTO(
                competition_id=torneo.value,
                team_a_captain_id=e.creadores[torneo].value,
                team_b_captain_id=otro.value,
            ),
            e.creadores[torneo],
        )

        assert len(e.lanzador.lanzadas) == 1

    async def test_al_reabrir_se_corta_la_que_este_a_medias(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)

        await ReopenEnrollmentsUseCase(e.uow).execute(
            ReopenEnrollmentsRequestDTO(competition_id=torneo.value), e.creadores[torneo]
        )

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.CORTADA

    async def test_al_iniciar_se_corta_la_que_este_a_medias(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)

        await e.iniciar(torneo)

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.CORTADA


class TestLaPasada:
    async def test_pregunta_por_cada_inscrito_con_pausa_y_queda_completa(self, e):
        torneo = await e.torneo()
        a, b = await e.inscrito(torneo), await e.inscrito(torneo)
        await e.cerrar(torneo)

        preguntados = await e.pasar(torneo)

        creador = e.creadores[torneo]
        assert preguntados == 3
        assert sorted(e.preguntados()) == sorted(e.nombre(u) for u in (creador, a, b))
        assert e.esperas == [PAUSA_ENTRE_JUGADORES] * 2
        assert await e.apuntado(torneo) == {
            u: Intento(ResultadoRefresco.ACTUALIZADO, 1) for u in (creador, a, b)
        }
        assert (await e.ultima(torneo)).estado is EstadoActualizacion.COMPLETA
        e.avisos.send_handicaps_pending_email.assert_not_awaited()

    async def test_con_personalizado_no_pregunta(self, e):
        torneo = await e.torneo()
        propio = await e.inscrito(torneo, personalizado=Decimal("18.0"))
        await e.cerrar(torneo)

        await e.pasar(torneo)

        assert e.nombre(propio) not in e.preguntados()

    async def test_si_la_rfeg_falla_lo_intenta_tres_veces_y_sigue(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)
        e.rfeg.search_handicap.side_effect = [TimeoutError, TimeoutError, 11.2]

        await e.pasar(torneo)

        assert e.esperas == [PAUSA_ENTRE_INTENTOS] * 2
        assert await e.apuntado(torneo) == {
            e.creadores[torneo]: Intento(ResultadoRefresco.ACTUALIZADO, 3)
        }
        assert (await e.ultima(torneo)).estado is EstadoActualizacion.COMPLETA

    async def test_si_falla_las_tres_veces_queda_incompleta_y_avisa(self, e):
        torneo = await e.torneo()
        roto = await e.inscrito(torneo)
        await e.cerrar(torneo)
        e.rfeg.search_handicap = AsyncMock(
            side_effect=lambda nombre: (
                (_ for _ in ()).throw(TimeoutError) if nombre == e.nombre(roto) else 11.2
            )
        )

        await e.pasar(torneo)

        assert (await e.apuntado(torneo))[roto] == Intento(ResultadoRefresco.FALLIDO, 3)
        assert (await e.ultima(torneo)).estado is EstadoActualizacion.INCOMPLETA
        creador = e.usuarios.por_id[e.creadores[torneo]]
        e.avisos.send_handicaps_pending_email.assert_awaited_once_with(
            to_email=creador.email.value,
            organizer_name=creador.get_full_name(),
            competition_name="Medal de octubre",  # el dominio lo guarda así
            competition_id=str(torneo.value),
            pending_names=[e.nombre(roto)],
        )

    async def test_una_a_medias_se_vuelve_a_pasar_solo_con_lo_que_falta(self, e):
        torneo = await e.torneo()
        roto = await e.inscrito(torneo)
        await e.cerrar(torneo)
        ultima = await e.ultima(torneo)
        await e.uow.handicap_updates.apuntar(
            ultima.id, e.creadores[torneo], ResultadoRefresco.ACTUALIZADO, AHORA
        )
        await e.uow.handicap_updates.apuntar(ultima.id, roto, ResultadoRefresco.FALLIDO, AHORA)

        assert await e.pasar(torneo) == 1
        assert e.preguntados() == [e.nombre(roto)]

    async def test_sin_licencia_espanola_se_apunta_sin_preguntar(self, e):
        torneo = await e.torneo()
        fuera = await e.inscrito(torneo, pais="FR")
        await e.cerrar(torneo)

        await e.pasar(torneo)

        assert e.nombre(fuera) not in e.preguntados()
        assert (await e.apuntado(torneo))[fuera] == Intento(
            ResultadoRefresco.SIN_LICENCIA_ESPANOLA, 1
        )

    async def test_una_que_ya_no_sigue_no_pregunta(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)
        await e.iniciar(torneo)

        assert await e.pasar(torneo) == 0
        assert e.preguntados() == []


class TestElHandicapFijado:
    async def test_en_un_stableford_cerrado_se_corrige_el_fijado_y_las_categorias(self, e):
        torneo = await e.torneo(tipo="STABLEFORD", limites=("12.0",))
        # El creador (10.0) y 5 más con 8.0: primera categoría; y 6 con 20.0
        bajos = [await e.inscrito(torneo, handicap=8.0) for _ in range(5)]
        altos = [await e.inscrito(torneo, handicap=20.0) for _ in range(6)]
        await e.cerrar(torneo)
        # La RFEG sube a 13.0 a uno de los bajos: ya no llegan a 6 y se juntan
        sube = bajos[0]
        e.rfeg.search_handicap = AsyncMock(
            side_effect=lambda nombre: 13.0 if nombre == e.nombre(sube) else None
        )

        await e.pasar(torneo)

        inscripciones = await e.inscripciones(torneo)
        assert inscripciones[sube].fixed_handicap == Decimal("13.0")
        assert inscripciones[altos[0]].fixed_handicap == Decimal("20.0")
        assert {i.fixed_category for i in inscripciones.values()} == {1}

    async def test_un_fijado_corregido_llega_a_su_partida_sin_salir(self, e):
        """G1 (#251, PR 4): mismas barras, otro hándicap de juego y otros golpes."""
        from src.modules.competition.domain.entities.partida import Partida
        from src.modules.competition.domain.value_objects.jugador_de_partida import (
            JugadorDePartida,
        )
        from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
        from src.shared.domain.value_objects.gender import Gender
        from tests.unit.modules.competition.application.services.test_jugadores_de_la_partida import (
            _campo,
        )

        torneo = await e.torneo(tipo="STABLEFORD")
        jugador = await e.inscrito(torneo, handicap=8.0)
        await e.cerrar(torneo)
        (franja,) = [r for r in await e.uow.rounds.find_by_competition(torneo) if r.hoja_de_salidas]

        def foto(user_id, handicap):
            return JugadorDePartida(
                user_id, Decimal(handicap), 0, TeeColor.YELLOW, Gender.MALE, (0,) * 18, (4,) * 18
            )

        await e.uow.partidas.anadir(
            [
                Partida.crear(
                    torneo, franja.id, 1, [foto(jugador, "8.0"), foto(e.creadores[torneo], "10.0")]
                )
            ]
        )
        e.campos = AsyncMock()
        e.campos.find_by_id.return_value = _campo()
        e.rfeg.search_handicap = AsyncMock(
            side_effect=lambda nombre: 13.0 if nombre == e.nombre(jugador) else None
        )

        await e.pasar(torneo)

        (partida,) = await e.uow.partidas.de_la_franja(franja.id)
        suyo = next(j for j in partida.jugadores if j.user_id == jugador)
        assert (suyo.handicap, suyo.tee_color) == (Decimal("13.0"), TeeColor.YELLOW)
        assert suyo.playing_handicap == sum(suyo.golpes_por_hoyo) > 0

    async def test_con_personalizado_en_otra_competicion_alli_no_se_toca(self, e):
        con_propio = await e.torneo(tipo="STABLEFORD")
        sin_propio = await e.torneo(tipo="STABLEFORD")
        jugador = await e.inscrito(sin_propio, handicap=8.0)
        await create_approved_enrollment(e.uow, con_propio.value, jugador, Decimal("18.0"))
        await e.cerrar(con_propio)
        await e.cerrar(sin_propio)

        await e.pasar(con_propio)
        await e.pasar(sin_propio)

        assert (await e.inscripciones(sin_propio))[jugador].fixed_handicap == Decimal("11.2")
        assert (await e.inscripciones(con_propio))[jugador].fixed_handicap == Decimal("18.0")

    async def test_si_empieza_a_mitad_para_y_lo_pendiente_no_se_toca(self, e):
        torneo = await e.torneo(tipo="STABLEFORD")
        segundo = await e.inscrito(torneo, handicap=8.0)
        await e.cerrar(torneo)

        async def contesta_y_empieza(nombre):
            # Con el primero ya contestado, el organizador inicia
            if (await e.uow.competitions.find_by_id(torneo)).status.value == "CLOSED":
                await e.iniciar(torneo)
            return 13.0

        e.rfeg.search_handicap = AsyncMock(side_effect=contesta_y_empieza)

        preguntados = await e.pasar(torneo)

        assert preguntados == 1
        assert (await e.inscripciones(torneo))[segundo].fixed_handicap == Decimal("8.0")
        assert (await e.ultima(torneo)).estado is EstadoActualizacion.CORTADA
        e.avisos.send_handicaps_pending_email.assert_not_awaited()

    async def test_si_se_corta_mientras_contesta_la_rfeg_no_corrige(self, e):
        torneo = await e.torneo(tipo="STABLEFORD")
        await e.cerrar(torneo)
        creador = e.creadores[torneo]
        primera = await e.ultima(torneo)

        async def reabre_cierra_y_contesta(nombre):
            # A la vez, el organizador reabre y vuelve a cerrar: esta se corta
            await e.mover(torneo, "reopen_enrollments")
            await e.cerrar(torneo)
            return 13.0

        e.rfeg.search_handicap = AsyncMock(side_effect=reabre_cierra_y_contesta)

        await e.caso().execute(primera.id)

        assert (await e.inscripciones(torneo))[creador].fixed_handicap == Decimal("10.0")

    async def test_si_se_corta_con_el_ultimo_no_avisa(self, e):
        torneo = await e.torneo(tipo="STABLEFORD")
        await e.cerrar(torneo)

        async def empieza_y_falla(nombre):
            if (await e.uow.competitions.find_by_id(torneo)).status.value == "CLOSED":
                await e.iniciar(torneo)
            raise TimeoutError

        e.rfeg.search_handicap = AsyncMock(side_effect=empieza_y_falla)

        await e.pasar(torneo)

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.CORTADA
        e.avisos.send_handicaps_pending_email.assert_not_awaited()

    async def test_si_se_corta_no_reintenta_con_ese_jugador(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)

        async def empieza_y_falla(nombre):
            if (await e.uow.competitions.find_by_id(torneo)).status.value == "CLOSED":
                await e.iniciar(torneo)
            raise TimeoutError

        e.rfeg.search_handicap = AsyncMock(side_effect=empieza_y_falla)

        await e.pasar(torneo)

        assert e.rfeg.search_handicap.await_count == 1

    async def test_en_una_ryder_solo_cambia_el_perfil(self, e):
        torneo = await e.torneo()
        jugador = await e.inscrito(torneo, handicap=8.0)
        await e.cerrar(torneo)

        await e.pasar(torneo)

        assert e.usuarios.por_id[jugador].handicap.value == 11.2
        assert (await e.inscripciones(torneo))[jugador].fixed_handicap is None


class TestLaVentanaCortaLaQueEstaEnMarcha:
    """
    «Se corta 10 s por jugador antes de empezar»: el botón Y la que esté en marcha
    (Agustín, 7 oct 2026). Lo pendiente se queda como estaba.
    """

    # El 12 a las 9:00 en Madrid son las 7:00 UTC; con 2 jugadores, se cierra 20 s antes
    CIERRE = datetime(2030, 10, 12, 6, 59, 40, tzinfo=UTC)

    async def test_si_se_cierra_a_mitad_no_pregunta_por_los_demas(self, e):
        torneo = await e.torneo(tipo="STABLEFORD")
        segundo = await e.inscrito(torneo, handicap=8.0)
        await e.franja(torneo)
        await e.cerrar(torneo)

        async def no_lo_encuentra_y_pasa_la_hora(nombre):
            # Sin hándicap nuevo no se corrige nada: lo para la comprobación de
            # antes de preguntar por el siguiente
            e.ahora = self.CIERRE

        e.rfeg.search_handicap = AsyncMock(side_effect=no_lo_encuentra_y_pasa_la_hora)

        preguntados = await e.pasar(torneo)

        assert preguntados == 1
        assert (await e.inscripciones(torneo))[segundo].fixed_handicap == Decimal("8.0")
        assert (await e.ultima(torneo)).estado is EstadoActualizacion.CORTADA
        e.avisos.send_handicaps_pending_email.assert_not_awaited()

    async def test_si_se_cierra_mientras_contesta_la_rfeg_no_cambia_nada(self, e):
        torneo = await e.torneo(tipo="STABLEFORD")
        await e.franja(torneo)
        await e.cerrar(torneo)
        creador = e.creadores[torneo]

        async def tarda_hasta_el_cierre(nombre):
            # A las 9:00 en Madrid ya ha salido la primera partida
            e.ahora = datetime(2030, 10, 12, 7, 0, tzinfo=UTC)
            return 13.0

        e.rfeg.search_handicap = AsyncMock(side_effect=tarda_hasta_el_cierre)

        await e.pasar(torneo)

        assert (await e.inscripciones(torneo))[creador].fixed_handicap == Decimal("10.0")
        assert (await e.ultima(torneo)).estado is EstadoActualizacion.CORTADA


class TestComo:
    async def test_la_rfeg_se_consulta_sin_ninguna_transaccion_abierta(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)
        abiertas = []

        async def mira(nombre):
            abiertas.append(e.uow.abiertas)
            return 11.2

        e.rfeg.search_handicap = AsyncMock(side_effect=mira)

        await e.pasar(torneo)

        assert abiertas == [0]

    async def test_un_fallo_inesperado_se_apunta_y_sigue_con_los_demas(self, e):
        torneo = await e.torneo()
        roto = await e.inscrito(torneo)
        await e.cerrar(torneo)
        original = e.usuarios.find_by_id

        async def revienta(user_id):
            if user_id == roto:
                raise RuntimeError("se cayó la base de datos")
            return await original(user_id)

        e.usuarios.find_by_id = revienta

        await e.pasar(torneo)

        apuntado = await e.apuntado(torneo)
        assert apuntado[roto] == Intento(ResultadoRefresco.FALLIDO, 3)
        assert apuntado[e.creadores[torneo]] == Intento(ResultadoRefresco.ACTUALIZADO, 1)


class TestCorregirDirectamente:
    """`HandicapsAlCerrar.corregir` protege lo suyo aunque se le llame desde otro sitio."""

    async def test_a_quien_tiene_personalizado_no_le_toca_el_fijado(self, e):
        torneo = await e.torneo(tipo="STABLEFORD")
        jugador = await e.inscrito(torneo, personalizado=Decimal("18.0"))
        await e.cerrar(torneo)
        competicion = await e.uow.competitions.find_by_id(torneo)

        await HandicapsAlCerrar(e.uow, e.usuarios).corregir(competicion, jugador, Decimal("2.0"))

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("18.0")


class TestCadaApunteConElCandado:
    """
    Todo apunte se hace con la competición bloqueada: así no se cuela entre la
    comprobación y el «cortada por un reinicio» del vigilante (CodeRabbit, #510).
    """

    def _espiar(self, e):
        bloqueos = []
        original = e.uow.competitions.find_by_id_for_update

        async def espia(competition_id):
            bloqueos.append(competition_id)
            return await original(competition_id)

        e.uow.competitions.find_by_id_for_update = espia
        # Solo cuenta el candado de la MISMA transacción que el apunte
        e.uow.al_abrir = bloqueos.clear
        return bloqueos

    async def test_tambien_lo_que_no_cambia_el_handicap(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)
        e.rfeg.search_handicap = AsyncMock(return_value=None)  # no lo encuentra
        bloqueos = self._espiar(e)
        original = e.uow.handicap_updates.apuntar
        sin_candado = []

        async def apuntar(*args):
            if not bloqueos:
                sin_candado.append(args)
            return await original(*args)

        e.uow.handicap_updates.apuntar = apuntar

        await e.pasar(torneo)

        assert sin_candado == []

    async def test_tambien_el_fallo_inesperado(self, e):
        torneo = await e.torneo()
        roto = await e.inscrito(torneo)
        await e.cerrar(torneo)
        original_usuario = e.usuarios.find_by_id

        async def revienta(user_id):
            if user_id == roto:
                raise RuntimeError("se cayó la base de datos")
            return await original_usuario(user_id)

        e.usuarios.find_by_id = revienta
        bloqueos = self._espiar(e)
        original = e.uow.handicap_updates.apuntar
        sin_candado = []

        async def apuntar(update_id, user_id, *args):
            if user_id == roto and not bloqueos:
                sin_candado.append(user_id)
            return await original(update_id, user_id, *args)

        e.uow.handicap_updates.apuntar = apuntar

        await e.pasar(torneo)

        assert sin_candado == []


class TestCategoriasIgualesTrasElRefrescoDelCierre:
    """
    El refresco del cierre llega siempre segundos después del reparto: al
    acabar, se reparte otra vez con los hándicaps corregidos (10 oct 2026).
    El botón y lo programado mantienen los límites.
    """

    async def _doce(self, e, torneo):
        """El creador (10,0), 5 con 8,0 y 6 con 20,0: al cerrar, «hasta 10,0»."""
        bajos = [await e.inscrito(torneo, handicap=8.0) for _ in range(5)]
        altos = [await e.inscrito(torneo, handicap=20.0) for _ in range(6)]
        return bajos, altos

    async def _limites(self, e, torneo):
        return (await e.uow.competitions.find_by_id(torneo)).stroke_play.category_limits

    def _la_rfeg_da(self, e, nuevos: dict) -> None:
        e.rfeg.search_handicap = AsyncMock(
            side_effect=lambda nombre: next(
                (h for u, h in nuevos.items() if nombre == e.nombre(u)), None
            )
        )

    async def test_al_acabar_el_del_cierre_se_reparte_otra_vez(self, e):
        torneo = await e.torneo(tipo="STABLEFORD", contador=2)
        bajos, altos = await self._doce(e, torneo)
        await e.cerrar(torneo)
        assert await self._limites(e, torneo) == (Decimal("10.0"),)
        # Tres de los bajos suben a 30,0: con los límites del cierre serían 3 y 9
        self._la_rfeg_da(e, dict.fromkeys(bajos[:3], 30.0))

        await e.pasar(torneo)

        # Ordenados: 8, 8, 10, 20×6, 30×3 → el 6.º es el 20,0 (con los del cierre
        # seguiría en 10,0). Los empatados en 20,0 van abajo y arriba quedan 3:
        # la regla de los seis los junta, y las categorías se fijan otra vez
        assert await self._limites(e, torneo) == (Decimal("20.0"),)
        inscripciones = await e.inscripciones(torneo)
        assert {inscripciones[u].fixed_category for u in [*altos, *bajos]} == {1}
        assert {inscripciones[u].fixed_handicap for u in bajos[:3]} == {Decimal("30.0")}

    async def test_si_queda_incompleta_tambien_se_reparte_con_lo_que_hay(self, e):
        torneo = await e.torneo(tipo="STABLEFORD", contador=2)
        bajos, _ = await self._doce(e, torneo)
        await e.cerrar(torneo)

        def contesta(nombre):
            if nombre == e.nombre(bajos[4]):
                raise RuntimeError("RFEG caída")
            return 30.0 if nombre in {e.nombre(u) for u in bajos[:3]} else None

        e.rfeg.search_handicap = AsyncMock(side_effect=contesta)

        await e.pasar(torneo)

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.INCOMPLETA
        assert await self._limites(e, torneo) == (Decimal("20.0"),)

    async def test_si_empieza_a_mitad_no_se_reparte(self, e):
        torneo = await e.torneo(tipo="STABLEFORD", contador=2)
        bajos, _ = await self._doce(e, torneo)
        await e.cerrar(torneo)
        ultima = await e.ultima(torneo)
        ultima.estado = EstadoActualizacion.CORTADA
        await e.uow.handicap_updates.update(ultima)
        self._la_rfeg_da(e, dict.fromkeys(bajos[:3], 30.0))

        await e.pasar(torneo)

        assert await self._limites(e, torneo) == (Decimal("10.0"),)

    async def test_la_del_boton_mantiene_los_limites(self, e):
        from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
            ActualizacionDeHandicaps,
        )

        torneo = await e.torneo(tipo="STABLEFORD", contador=2)
        bajos, _ = await self._doce(e, torneo)
        await e.cerrar(torneo)
        del_cierre = await e.ultima(torneo)
        del_cierre.estado = EstadoActualizacion.COMPLETA
        await e.uow.handicap_updates.update(del_cierre)
        boton = ActualizacionDeHandicaps.crear(torneo, OrigenActualizacion.BOTON, e.ahora)
        await e.uow.handicap_updates.add(boton)
        self._la_rfeg_da(e, dict.fromkeys(bajos[:3], 30.0))

        await e.caso().execute(boton.id)

        assert await self._limites(e, torneo) == (Decimal("10.0"),)
        inscripciones = await e.inscripciones(torneo)
        assert {inscripciones[u].fixed_handicap for u in bajos[:3]} == {Decimal("30.0")}

    async def test_con_limites_a_mano_no_se_tocan(self, e):
        torneo = await e.torneo(tipo="STABLEFORD", limites=("12.0",))
        bajos, _ = await self._doce(e, torneo)
        await e.cerrar(torneo)
        self._la_rfeg_da(e, dict.fromkeys(bajos[:3], 30.0))

        await e.pasar(torneo)

        assert await self._limites(e, torneo) == (Decimal("12.0"),)


class TestSinActualizarConLaRfeg:
    """Lo que se avisa al terminar, según quién se quedó sin actualizar (H1-H6)."""

    def _no_encuentra(self, e, *quienes):
        """La RFEG no encuentra a esos; a los demás, sí."""
        nombres = {e.nombre(u) for u in quienes}
        e.rfeg.search_handicap = AsyncMock(
            side_effect=lambda nombre: None if nombre in nombres else 11.2
        )

    def _falla_con(self, e, *quienes):
        """La RFEG falla con esos; a los demás los encuentra."""
        nombres = {e.nombre(u) for u in quienes}

        async def buscar(nombre):
            if nombre in nombres:
                raise TimeoutError
            return 11.2

        e.rfeg.search_handicap = AsyncMock(side_effect=buscar)

    def _organizador(self, e, torneo):
        return e.usuarios.por_id[e.creadores[torneo]]

    async def _competicion(self, e, torneo):
        return await e.uow.competitions.find_by_id(torneo)

    async def test_todos_actualizados_no_avisa_a_nadie(self, e):
        """
        Given una competición en la que la RFEG encuentra a todos
        When termina la pasada
        Then no se avisa a nadie (H1)
        """
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.cerrar(torneo)

        await e.pasar(torneo)

        e.avisos.send_handicaps_pending_email.assert_not_awaited()
        e.avisos.send_handicap_not_found_email.assert_not_awaited()
        e.actividad.handicaps_not_updated.assert_not_awaited()
        e.actividad.handicap_not_found.assert_not_awaited()

    async def test_espanol_no_encontrado_avisa_al_organizador_y_a_el(self, e):
        """
        Given un español al que la RFEG no encuentra
        When termina la pasada (completa: no encontrado es una respuesta)
        Then el organizador recibe correo y aviso con él, y él su correo y su aviso (H2, H3)
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)

        await e.pasar(torneo)

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.COMPLETA
        organizador = self._organizador(e, torneo)
        e.avisos.send_handicaps_pending_email.assert_awaited_once_with(
            to_email=organizador.email.value,
            organizer_name=organizador.get_full_name(),
            competition_name="Medal de octubre",
            competition_id=str(torneo.value),
            pending_names=[e.nombre(perdido)],
        )
        competicion = await self._competicion(e, torneo)
        e.actividad.handicaps_not_updated.assert_awaited_once_with(competicion, 1)
        jugador = e.usuarios.por_id[perdido]
        e.avisos.send_handicap_not_found_email.assert_awaited_once_with(
            to_email=jugador.email.value,
            player_name=jugador.get_full_name(),
            competition_name="Medal de octubre",
        )
        e.actividad.handicap_not_found.assert_awaited_once_with(competicion, [perdido])

    async def test_si_la_rfeg_falla_avisa_al_organizador_pero_al_jugador_no(self, e):
        """
        Given un español con el que la RFEG falla las tres veces
        When termina la pasada (incompleta)
        Then el organizador lo tiene en su lista, y el jugador no recibe nada (H4)
        """
        torneo = await e.torneo()
        roto = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._falla_con(e, roto)

        await e.pasar(torneo)

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.INCOMPLETA
        assert e.avisos.send_handicaps_pending_email.await_args.kwargs["pending_names"] == [
            e.nombre(roto)
        ]
        e.actividad.handicaps_not_updated.assert_awaited_once_with(
            await self._competicion(e, torneo), 1
        )
        e.avisos.send_handicap_not_found_email.assert_not_awaited()
        e.actividad.handicap_not_found.assert_not_awaited()

    async def test_extranjero_en_espana_va_a_la_lista_del_organizador(self, e):
        """
        Given un extranjero (sin licencia española) en una competición en España
        When termina la pasada
        Then sale en la lista del organizador, y él no recibe nada (H2, H6)
        """
        torneo = await e.torneo(pais="ES")
        fuera = await e.inscrito(torneo, pais="FR")
        await e.cerrar(torneo)

        await e.pasar(torneo)

        assert e.avisos.send_handicaps_pending_email.await_args.kwargs["pending_names"] == [
            e.nombre(fuera)
        ]
        e.actividad.handicaps_not_updated.assert_awaited_once()
        e.avisos.send_handicap_not_found_email.assert_not_awaited()
        e.actividad.handicap_not_found.assert_not_awaited()

    async def test_extranjero_fuera_de_espana_no_avisa(self, e):
        """
        Given un extranjero en una competición fuera de España
        When termina la pasada
        Then no se avisa a nadie (H2, H6)
        """
        torneo = await e.torneo(pais="FR")
        await e.inscrito(torneo, pais="FR")
        await e.cerrar(torneo)

        await e.pasar(torneo)

        e.avisos.send_handicaps_pending_email.assert_not_awaited()
        e.actividad.handicaps_not_updated.assert_not_awaited()
        e.avisos.send_handicap_not_found_email.assert_not_awaited()

    async def test_espanol_no_encontrado_fuera_de_espana_tambien(self, e):
        """
        Given un español al que la RFEG no encuentra, en una competición fuera de España
        When termina la pasada
        Then el organizador lo tiene en su lista y él recibe su aviso (H2, H3)
        """
        torneo = await e.torneo(pais="FR")
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)

        await e.pasar(torneo)

        assert e.avisos.send_handicaps_pending_email.await_args.kwargs["pending_names"] == [
            e.nombre(perdido)
        ]
        e.actividad.handicap_not_found.assert_awaited_once_with(
            await self._competicion(e, torneo), [perdido]
        )

    async def test_otra_pasada_avisa_al_organizador_y_no_repite_al_jugador(self, e):
        """
        Given una pasada que deja a uno no encontrado y a otro con la RFEG caída
        When otra pasada de la incompleta encuentra al segundo
        Then el organizador recibe otra vez su lista, ya al día, y al no encontrado
             no se le repite el aviso (H1)
        """
        torneo = await e.torneo()
        perdido, roto = await e.inscrito(torneo), await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)
        nombres = {e.nombre(roto)}
        primera = e.rfeg.search_handicap.side_effect

        async def buscar(nombre):
            if nombre in nombres:
                raise TimeoutError
            return primera(nombre)

        e.rfeg.search_handicap = AsyncMock(side_effect=buscar)
        await e.pasar(torneo)
        ultima = await e.ultima(torneo)
        ultima.reanudar(e.ahora)
        await e.uow.handicap_updates.update(ultima)
        nombres.clear()

        await e.pasar(torneo)

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.COMPLETA
        listas = [
            c.kwargs["pending_names"] for c in e.avisos.send_handicaps_pending_email.await_args_list
        ]
        assert listas == [
            [e.nombre(perdido), e.nombre(roto)],
            [e.nombre(perdido)],
        ]
        assert [c.args[1] for c in e.actividad.handicaps_not_updated.await_args_list] == [2, 1]
        assert e.avisos.send_handicap_not_found_email.await_count == 1
        assert e.actividad.handicap_not_found.await_count == 1

    async def test_si_se_corta_no_avisa_a_nadie(self, e):
        """
        Given una pasada con un no encontrado y la competición que empieza a mitad
        When la pasada se corta
        Then no se avisa a nadie (H1: solo al terminar)
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)
        await e.iniciar(torneo)

        await e.pasar(torneo)

        e.avisos.send_handicaps_pending_email.assert_not_awaited()
        e.actividad.handicaps_not_updated.assert_not_awaited()
        e.avisos.send_handicap_not_found_email.assert_not_awaited()
        e.actividad.handicap_not_found.assert_not_awaited()

    async def test_correo_y_actividad_caidos_no_tumban_la_pasada(self, e):
        """
        Given el correo y Actividad caídos
        When termina con un no encontrado
        Then la pasada acaba igual y queda completa
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)
        e.avisos.send_handicaps_pending_email = AsyncMock(side_effect=RuntimeError)
        e.avisos.send_handicap_not_found_email = AsyncMock(side_effect=RuntimeError)
        e.actividad.handicaps_not_updated = AsyncMock(side_effect=RuntimeError)
        e.actividad.handicap_not_found = AsyncMock(side_effect=RuntimeError)

        assert await e.pasar(torneo) == 2

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.COMPLETA
        e.actividad.handicap_not_found.assert_awaited_once()

    async def _nueva(self, e, torneo):
        """Otra actualización de la competición (el botón o una programada)."""
        nueva = ActualizacionDeHandicaps.crear(torneo, OrigenActualizacion.BOTON, e.ahora)
        await e.uow.handicap_updates.add(nueva)
        return nueva

    async def _reanudar(self, e, torneo):
        ultima = await e.ultima(torneo)
        ultima.reanudar(e.ahora)
        await e.uow.handicap_updates.update(ultima)

    async def test_otra_actualizacion_que_no_lo_encuentra_no_le_escribe_otra_vez(self, e):
        """
        Given un español al que la RFEG no encontró y ya recibió su correo
        When otra actualización (el botón) tampoco lo encuentra
        Then se le renueva el aviso de Actividad, pero no recibe otro correo (D2)
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)
        await e.pasar(torneo)
        await self._nueva(e, torneo)

        await e.pasar(torneo)

        assert e.avisos.send_handicap_not_found_email.await_count == 1
        assert e.actividad.handicap_not_found.await_count == 2

    async def test_la_misma_lista_no_se_le_vuelve_a_mandar_al_organizador(self, e):
        """
        Given un organizador al que ya se le mandó la lista con un no encontrado
        When otra actualización deja la misma lista
        Then no recibe el mismo correo otra vez, pero su aviso se renueva (D2)
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)
        await e.pasar(torneo)
        await self._nueva(e, torneo)

        await e.pasar(torneo)

        assert e.avisos.send_handicaps_pending_email.await_count == 1
        assert [c.args[1] for c in e.actividad.handicaps_not_updated.await_args_list] == [1, 1]

    async def test_si_la_lista_cambia_se_le_manda_otra_vez(self, e):
        """
        Given la lista enviada con un no encontrado
        When otra actualización deja además a otro sin actualizar
        Then el organizador recibe la nueva lista (D2)
        """
        torneo = await e.torneo()
        perdido, otro = await e.inscrito(torneo), await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)
        await e.pasar(torneo)
        await self._nueva(e, torneo)
        self._no_encuentra(e, perdido, otro)

        await e.pasar(torneo)

        listas = [
            c.kwargs["pending_names"] for c in e.avisos.send_handicaps_pending_email.await_args_list
        ]
        assert listas == [[e.nombre(perdido)], [e.nombre(perdido), e.nombre(otro)]]

    async def test_si_la_lista_se_vacia_y_vuelve_se_manda_otra_vez(self, e):
        """
        Given una lista enviada que luego se vació (todos actualizados)
        When vuelve a quedar la misma
        Then se le manda otra vez: ya no es la última que recibió (D2)
        """
        torneo = await e.torneo()
        roto = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._falla_con(e, roto)
        await e.pasar(torneo)
        await self._nueva(e, torneo)
        self._falla_con(e)
        await e.pasar(torneo)
        await self._nueva(e, torneo)
        self._falla_con(e, roto)

        await e.pasar(torneo)

        assert e.avisos.send_handicaps_pending_email.await_count == 2

    async def test_si_otra_pasada_deja_a_todos_actualizados_se_retiran_los_avisos(self, e):
        """
        Given una pasada que deja a uno con la RFEG caída
        When otra pasada de la incompleta lo actualiza
        Then se retira el aviso del organizador y el de los jugadores (D3)
        """
        torneo = await e.torneo()
        roto = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._falla_con(e, roto)
        await e.pasar(torneo)
        e.actividad.handicaps_not_updated_withdrawn.assert_not_awaited()
        await self._reanudar(e, torneo)
        self._falla_con(e)

        await e.pasar(torneo)

        competicion = await self._competicion(e, torneo)
        e.actividad.handicaps_not_updated_withdrawn.assert_awaited_once_with(competicion)
        e.actividad.handicap_not_found_withdrawn.assert_awaited_with(
            competicion, [e.creadores[torneo], roto]
        )

    async def test_al_encontrarlo_en_otra_actualizacion_se_le_retira_el_suyo(self, e):
        """
        Given un no encontrado con su aviso
        When otra actualización sí lo encuentra
        Then se le retira su aviso y no le llega otro (D3)
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)
        await e.pasar(torneo)
        await self._nueva(e, torneo)
        self._no_encuentra(e)

        await e.pasar(torneo)

        assert e.actividad.handicap_not_found.await_count == 1
        retirados = e.actividad.handicap_not_found_withdrawn.await_args.args[1]
        assert perdido in retirados

    @pytest.mark.parametrize("donde", ["al_montar_actividad", "al_cerrar_actividad"])
    async def test_si_actividad_falla_la_pasada_acaba_igual(self, e, donde):
        """
        Given Actividad que falla al montarse o al cerrarse
        When termina una pasada con un no encontrado
        Then la pasada acaba completa, con sus correos, y dice a cuántos preguntó (T1)
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        self._no_encuentra(e, perdido)
        setattr(e, donde, RuntimeError("actividad caida"))

        assert await e.pasar(torneo) == 2

        assert (await e.ultima(torneo)).estado is EstadoActualizacion.COMPLETA
        e.avisos.send_handicaps_pending_email.assert_awaited_once()
        e.avisos.send_handicap_not_found_email.assert_awaited_once()

    async def test_actividad_se_monta_solo_al_avisar(self, e):
        """
        Given una pasada que se corta antes de acabar
        When se pasa
        Then no se monta Actividad (nada que avisar), y al acabar se monta una vez (T1)
        """
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.cerrar(torneo)
        await e.iniciar(torneo)

        await e.pasar(torneo)

        assert e.actividades_montadas == 0


class TestDesdeSuPerfil:
    """La RFEG encuentra su hándicap desde su perfil o al entrar (D1 y D4)."""

    async def _desde_su_perfil(self, e, user_id, handicap="13.0"):
        await HandicapDeLaRfegDelPerfilUseCase(
            herramientas=e.herramientas, reloj=lambda: e.ahora, actividad=e.fabrica_de_actividad
        ).execute(user_id, Decimal(handicap))

    async def test_queda_apuntado_como_actualizado(self, e):
        """
        Given un no encontrado en una competición cerrada
        When la RFEG lo encuentra desde su perfil
        Then queda apuntado como actualizado en la última actualización (D1)
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        e.rfeg.search_handicap = AsyncMock(return_value=None)
        await e.pasar(torneo)

        await self._desde_su_perfil(e, perdido)

        assert (await e.apuntado(torneo))[perdido].resultado is ResultadoRefresco.ACTUALIZADO

    async def test_en_un_stableford_cerrado_corrige_el_fijado_y_las_categorias(self, e):
        """
        Given un Stableford cerrado con dos categorías justas
        When la RFEG le da a uno otro hándicap desde su perfil
        Then su fijado cambia y las categorías se rehacen, como en la pasada (D4)
        """
        torneo = await e.torneo(tipo="STABLEFORD", limites=("12.0",))
        bajos = [await e.inscrito(torneo, handicap=8.0) for _ in range(5)]
        altos = [await e.inscrito(torneo, handicap=20.0) for _ in range(6)]
        await e.cerrar(torneo)

        await self._desde_su_perfil(e, bajos[0])

        inscripciones = await e.inscripciones(torneo)
        assert inscripciones[bajos[0]].fixed_handicap == Decimal("13.0")
        assert inscripciones[altos[0]].fixed_handicap == Decimal("20.0")
        assert {i.fixed_category for i in inscripciones.values()} == {1}

    async def test_su_partida_sin_salir_tambien(self, e):
        """Given su partida sin salir When la RFEG lo da desde su perfil Then su juego cambia (D4)."""
        from src.modules.competition.domain.entities.partida import Partida
        from src.modules.competition.domain.value_objects.jugador_de_partida import (
            JugadorDePartida,
        )
        from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
        from src.shared.domain.value_objects.gender import Gender
        from tests.unit.modules.competition.application.services.test_jugadores_de_la_partida import (
            _campo,
        )

        torneo = await e.torneo(tipo="STABLEFORD")
        jugador = await e.inscrito(torneo, handicap=8.0)
        await e.cerrar(torneo)
        (franja,) = [r for r in await e.uow.rounds.find_by_competition(torneo) if r.hoja_de_salidas]

        def foto(user_id, handicap):
            return JugadorDePartida(
                user_id, Decimal(handicap), 0, TeeColor.YELLOW, Gender.MALE, (0,) * 18, (4,) * 18
            )

        await e.uow.partidas.anadir(
            [
                Partida.crear(
                    torneo, franja.id, 1, [foto(jugador, "8.0"), foto(e.creadores[torneo], "10.0")]
                )
            ]
        )
        e.campos = AsyncMock()
        e.campos.find_by_id.return_value = _campo()

        await self._desde_su_perfil(e, jugador)

        (partida,) = await e.uow.partidas.de_la_franja(franja.id)
        suyo = next(j for j in partida.jugadores if j.user_id == jugador)
        assert suyo.handicap == Decimal("13.0")
        assert suyo.playing_handicap == sum(suyo.golpes_por_hoyo) > 0

    async def test_con_personalizado_el_fijado_no_se_toca(self, e):
        """Given un hándicap personalizado When la RFEG lo da Then el fijado sigue (D4)."""
        torneo = await e.torneo(tipo="STABLEFORD")
        propio = await e.inscrito(torneo, personalizado=Decimal("5.0"), handicap=8.0)
        await e.cerrar(torneo)

        await self._desde_su_perfil(e, propio)

        assert (await e.inscripciones(torneo))[propio].fixed_handicap == Decimal("5.0")

    async def test_ya_en_juego_no_hace_nada(self, e):
        """Given la competición ya empezada When la RFEG lo da Then ni se apunta ni se corrige."""
        torneo = await e.torneo(tipo="STABLEFORD")
        jugador = await e.inscrito(torneo, handicap=8.0)
        await e.cerrar(torneo)
        await e.pasar(torneo)
        await e.iniciar(torneo)
        antes = (await e.apuntado(torneo))[jugador]

        await self._desde_su_perfil(e, jugador)

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("11.2")
        assert (await e.apuntado(torneo))[jugador] == antes

    async def test_con_la_ventana_cerrada_se_apunta_pero_no_se_corrige(self, e):
        """
        Given un Stableford cerrado cuya primera salida ya pasó
        When la RFEG lo da desde su perfil
        Then se apunta como actualizado, pero el fijado no se toca (como en la pasada)
        """
        torneo = await e.torneo(tipo="STABLEFORD")
        jugador = await e.inscrito(torneo, handicap=8.0)
        await e.franja(torneo)
        await e.cerrar(torneo)
        # La franja sale el 12 a las 9:00 en Madrid (7:00 UTC): quedan 10 s
        e.ahora = datetime(2030, 10, 12, 6, 59, 50, tzinfo=UTC)

        await self._desde_su_perfil(e, jugador)

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("8.0")
        assert (await e.apuntado(torneo))[jugador].resultado is ResultadoRefresco.ACTUALIZADO

    async def test_sin_aprobar_no_hace_nada(self, e):
        """Given una inscripción que no está aprobada When la RFEG lo da Then nada."""
        torneo = await e.torneo(tipo="STABLEFORD")
        jugador = await e.inscrito(torneo, handicap=8.0)
        await e.cerrar(torneo)
        suya = (await e.inscripciones(torneo))[jugador]
        suya.withdraw()
        await e.uow.enrollments.update(suya)

        await self._desde_su_perfil(e, jugador)

        assert jugador not in await e.apuntado(torneo)

    async def test_en_una_ryder_solo_se_apunta(self, e):
        """Given una Ryder cerrada When la RFEG lo da Then se apunta; no hay fijado que tocar."""
        torneo = await e.torneo()
        jugador = await e.inscrito(torneo)
        await e.cerrar(torneo)

        await self._desde_su_perfil(e, jugador)

        assert (await e.apuntado(torneo))[jugador].resultado is ResultadoRefresco.ACTUALIZADO
        assert (await e.inscripciones(torneo))[jugador].fixed_handicap is None

    async def test_era_el_unico_se_retiran_el_suyo_y_el_del_organizador(self, e):
        """
        Given el único no encontrado de una competición, ya avisado
        When la RFEG lo encuentra desde su perfil
        Then se le retira su aviso y el del organizador, en ese momento (D3)
        """
        torneo = await e.torneo()
        perdido = await e.inscrito(torneo)
        await e.cerrar(torneo)
        e.rfeg.search_handicap = AsyncMock(
            side_effect=lambda nombre: None if nombre == e.nombre(perdido) else 11.2
        )
        await e.pasar(torneo)
        e.actividad.reset_mock()

        await self._desde_su_perfil(e, perdido)

        competicion = await e.uow.competitions.find_by_id(torneo)
        e.actividad.handicap_not_found_withdrawn.assert_awaited_once_with(competicion, [perdido])
        e.actividad.handicaps_not_updated_withdrawn.assert_awaited_once_with(competicion)
        e.actividad.handicaps_not_updated.assert_not_awaited()

    async def test_si_quedan_otros_el_organizador_ve_el_nuevo_numero(self, e):
        """
        Given dos no encontrados
        When la RFEG encuentra a uno desde su perfil
        Then se le retira el suyo y el organizador pasa a ver 1 (D3)
        """
        torneo = await e.torneo()
        perdido, otro = await e.inscrito(torneo), await e.inscrito(torneo)
        await e.cerrar(torneo)
        perdidos = {e.nombre(perdido), e.nombre(otro)}
        e.rfeg.search_handicap = AsyncMock(
            side_effect=lambda nombre: None if nombre in perdidos else 11.2
        )
        await e.pasar(torneo)
        e.actividad.reset_mock()

        await self._desde_su_perfil(e, perdido)

        competicion = await e.uow.competitions.find_by_id(torneo)
        e.actividad.handicap_not_found_withdrawn.assert_awaited_once_with(competicion, [perdido])
        e.actividad.handicaps_not_updated.assert_awaited_once_with(competicion, 1)
        e.actividad.handicaps_not_updated_withdrawn.assert_not_awaited()

    async def test_con_la_primera_pasada_en_curso_el_organizador_espera(self, e):
        """
        Given la actualización del cierre todavía en curso
        When la RFEG lo encuentra desde su perfil
        Then se retira el suyo, pero el del organizador lo dirá la pasada al acabar (H1)
        """
        torneo = await e.torneo()
        jugador = await e.inscrito(torneo)
        await e.cerrar(torneo)

        await self._desde_su_perfil(e, jugador)

        competicion = await e.uow.competitions.find_by_id(torneo)
        e.actividad.handicap_not_found_withdrawn.assert_awaited_once_with(competicion, [jugador])
        e.actividad.handicaps_not_updated.assert_not_awaited()
        e.actividad.handicaps_not_updated_withdrawn.assert_not_awaited()

    @pytest.mark.parametrize("donde", ["al_montar_actividad", "al_cerrar_actividad"])
    async def test_si_actividad_falla_el_fijado_se_corrige_igual(self, e, donde):
        """Given Actividad caída When la RFEG lo da desde su perfil Then el fijado cambia (T1)."""
        torneo = await e.torneo(tipo="STABLEFORD")
        jugador = await e.inscrito(torneo, handicap=8.0)
        await e.cerrar(torneo)
        setattr(e, donde, RuntimeError("actividad caida"))

        await self._desde_su_perfil(e, jugador)

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("13.0")

    async def test_sin_actividad_tambien(self, e):
        """Given sin Actividad (los tests y el Kind) When la RFEG lo da Then se apunta igual."""
        torneo = await e.torneo()
        jugador = await e.inscrito(torneo)
        await e.cerrar(torneo)

        await HandicapDeLaRfegDelPerfilUseCase(
            herramientas=e.herramientas, reloj=lambda: e.ahora
        ).execute(jugador, Decimal("13.0"))

        assert (await e.apuntado(torneo))[jugador].resultado is ResultadoRefresco.ACTUALIZADO

    async def test_sin_competiciones_no_monta_actividad(self, e):
        """Given un jugador sin competiciones cerradas When la RFEG lo da Then no se monta nada."""
        torneo = await e.torneo()
        jugador = await e.inscrito(torneo)

        await self._desde_su_perfil(e, jugador)

        assert e.actividades_montadas == 0
