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

    async def __aenter__(self):
        self.abiertas += 1
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
        self.lanzador = _Lanzador(self.uow)
        self.esperas: list[float] = []
        self.creadores: dict[CompetitionId, UserId] = {}
        self.ahora = AHORA

    async def esperar(self, segundos: float) -> None:
        self.esperas.append(segundos)

    async def torneo(self, tipo="RYDER_CUP", limites=("12.0",)) -> CompetitionId:
        """Una competición con las inscripciones abiertas; su creador, sin personalizado."""
        creador = self.usuarios.alta()
        extra = {}
        if tipo != "RYDER_CUP":
            extra["stroke_play"] = StrokePlaySettingsDTO(
                category_limits=[Decimal(x) for x in limites]
            )
        respuesta = await CreateCompetitionUseCase(
            self.uow, LocationBuilder(self.uow.countries), self.usuarios
        ).execute(
            CreateCompetitionRequestDTO(
                name="Medal de octubre",
                start_date=date(2030, 10, 12),
                end_date=date(2030, 10, 12),
                main_country="ES",
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
        await CloseEnrollmentsUseCase(
            self.uow, self.usuarios, self.lanzador if lanzador else None
        ).execute(CloseEnrollmentsRequestDTO(competition_id=torneo.value), self.creadores[torneo])

    async def iniciar(self, torneo) -> None:
        await montar_calendario(self.uow, torneo.value, "sin jugar")
        await StartCompetitionUseCase(self.uow).execute(
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
        yield Herramientas(competiciones=self.uow, usuarios=self.usuarios, zonas=_Madrid())

    def caso(self) -> RefrescarHandicapsUseCase:
        return RefrescarHandicapsUseCase(
            herramientas=self.herramientas,
            handicap_service=self.rfeg,
            avisos=self.avisos,
            reloj=lambda: self.ahora,
            esperar=self.esperar,
        )

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
            competition_name="Medal De Octubre",  # el dominio lo guarda así
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
