"""
El refresco de las 3:00 de cada día de juego, de punta a punta (BE #502).

Lo lanza el vigilante cada 15 minutos. Busca los torneos que juegan hoy en el
huso de su campo, pregunta a la RFEG por quien juega y todavía no ha empezado,
uno a uno y con pausa, y apunta qué pasó con cada uno.
"""

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.application.use_cases.refrescar_handicaps_del_dia_use_case import (
    PAUSA_ENTRE_CONSULTAS,
    Herramientas,
    RefrescarHandicapsDelDiaUseCase,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio

MADRID = ZoneInfo("Europe/Madrid")
SABADO = date(2030, 10, 12)


def _hora_de_madrid(hora: int, minuto: int = 0, dia: date = SABADO) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=MADRID).astimezone(UTC)


def _campo():
    """El mismo campo de mentira que usan los tests de la generación de partidos."""
    tee = MagicMock()
    tee.color = TeeColor.YELLOW
    tee.gender = Gender.MALE
    tee.course_rating = Decimal("71.2")
    tee.slope_rating = 128
    hoyos = []
    for numero in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = numero
        hoyo.par = 4
        hoyo.stroke_index = numero
        hoyos.append(hoyo)
    campo = MagicMock()
    campo.tees = [tee]
    campo.reference_card = hoyos
    return campo


class _Usuarios:
    """Los jugadores, con lo que mira el refresco: país, nombre y hándicap."""

    def __init__(self):
        self.por_id: dict[UserId, MagicMock] = {}
        self.save = AsyncMock()

    def alta(self, pais: str = "ES") -> UserId:
        user_id = UserId.generate()
        usuario = MagicMock()
        usuario.id = user_id
        usuario.country_code = MagicMock(value=pais)
        usuario.handicap_updated_at = None
        usuario.handicap = MagicMock(value=10.0)
        usuario.gender = Gender.MALE
        usuario.get_full_name.return_value = f"Jugador {user_id}"

        def actualizar(valor, usuario=usuario):
            usuario.handicap = MagicMock(value=valor)

        usuario.update_handicap.side_effect = actualizar
        self.por_id[user_id] = usuario
        return user_id

    def con_handicap(self, user_id: UserId, valor: float) -> None:
        self.por_id[user_id].handicap = MagicMock(value=valor)

    async def find_by_ids(self, user_ids):
        return [self.por_id[u] for u in user_ids if u in self.por_id]

    async def find_by_id(self, user_id: UserId):
        return self.por_id.get(user_id)


class _UnidadQueCuenta(InMemoryUnitOfWork):
    """Sabe si hay una transacción abierta, para ver dónde se pregunta a la RFEG."""

    def __init__(self):
        super().__init__()
        self.abiertas = 0
        self.savepoints = 0

    @asynccontextmanager
    async def savepoint(self):
        self.savepoints += 1
        async with super().savepoint():
            yield

    async def __aenter__(self):
        self.abiertas += 1
        return await super().__aenter__()

    async def __aexit__(self, *args):
        self.abiertas -= 1
        return await super().__aexit__(*args)


class _Escenario:
    def __init__(self):
        self.uow = _UnidadQueCuenta()
        self.herramientas_pedidas = 0
        self.usuarios = _Usuarios()
        self.rfeg = MagicMock()
        self.rfeg.search_handicap = AsyncMock(return_value=11.2)
        self.zona = MagicMock()
        self.zona.for_course = AsyncMock(return_value="Europe/Madrid")
        self.campos = MagicMock()
        self.campos.find_by_id = AsyncMock(return_value=_campo())
        self.esperas: list[float] = []

    async def esperar(self, segundos: float) -> None:
        self.esperas.append(segundos)

    async def torneo(self, estado: str | None = None) -> CompetitionId:
        respuesta = await create_competition(self.uow, UserId.generate())
        if estado:
            await set_competition_status(self.uow, respuesta.id, estado)
        return CompetitionId(respuesta.id)

    async def inscrito(self, torneo, pais="ES", personalizado=None) -> UserId:
        user_id = self.usuarios.alta(pais)
        await create_approved_enrollment(self.uow, torneo.value, user_id, personalizado)
        return user_id

    async def sesion(self, torneo, dia=SABADO) -> Round:
        ronda = Round.create(
            competition_id=torneo,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=dia,
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with self.uow:
            await self.uow.rounds.add(ronda)
        return ronda

    async def partido(self, ronda, a: UserId, b: UserId, empezado=False) -> Match:
        def jugador(user_id):
            return MatchPlayer.create(
                user_id=user_id,
                playing_handicap=10,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
                strokes_received=[],
            )

        partido = Match.create(
            round_id=ronda.id,
            match_number=1,
            team_a_players=[jugador(a)],
            team_b_players=[jugador(b)],
        )
        if empezado:
            partido.start()
        async with self.uow:
            await self.uow.matches.add(partido)
        return partido

    @asynccontextmanager
    async def herramientas(self):
        self.herramientas_pedidas += 1
        yield Herramientas(
            competiciones=self.uow, usuarios=self.usuarios, zonas=self.zona, campos=self.campos
        )

    def caso(self, ahora: datetime) -> RefrescarHandicapsDelDiaUseCase:
        return RefrescarHandicapsDelDiaUseCase(
            herramientas=self.herramientas,
            handicap_service=self.rfeg,
            reloj=lambda: ahora,
            esperar=self.esperar,
        )

    def preguntados(self) -> set[str]:
        return {llamada.args[0] for llamada in self.rfeg.search_handicap.await_args_list}

    def nombre(self, user_id: UserId) -> str:
        return f"Jugador {user_id}"


@pytest.fixture
def e() -> _Escenario:
    return _Escenario()


class TestCuando:
    async def test_a_las_tres_del_dia_de_juego_pregunta_por_quien_juega(self, e):
        torneo = await e.torneo()
        a, b = await e.inscrito(torneo), await e.inscrito(torneo)
        await e.partido(await e.sesion(torneo), a, b)

        await e.caso(_hora_de_madrid(3, 5)).execute()

        assert e.preguntados() == {e.nombre(a), e.nombre(b)}
        assert await e.uow.handicap_refreshes.del_dia(torneo, SABADO) == {
            a: ResultadoRefresco.ACTUALIZADO,
            b: ResultadoRefresco.ACTUALIZADO,
        }

    async def test_antes_de_las_tres_no(self, e):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo)

        await e.caso(_hora_de_madrid(2, 59)).execute()

        assert e.preguntados() == set()

    @pytest.mark.parametrize("dia", [date(2030, 10, 11), date(2030, 10, 13)])
    async def test_un_torneo_que_no_juega_hoy_no(self, e, dia):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo, dia=dia)

        await e.caso(_hora_de_madrid(4)).execute()

        assert e.preguntados() == set()

    @pytest.mark.parametrize("estado", ["CANCELLED", "COMPLETED"])
    async def test_un_torneo_cancelado_o_terminado_no(self, e, estado):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo)
        await set_competition_status(e.uow, torneo.value, estado)

        await e.caso(_hora_de_madrid(4)).execute()

        assert e.preguntados() == set()

    async def test_sin_zona_del_campo_no_se_sabe_que_hora_es_alli(self, e):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo)
        e.zona.for_course = AsyncMock(return_value=None)

        await e.caso(_hora_de_madrid(4)).execute()

        assert e.preguntados() == set()


class TestAQuien:
    async def test_sin_partidos_de_hoy_todavia_a_todos_los_inscritos(self, e):
        torneo = await e.torneo()
        a, b = await e.inscrito(torneo), await e.inscrito(torneo)
        await e.sesion(torneo)

        await e.caso(_hora_de_madrid(3)).execute()

        assert e.preguntados() == {e.nombre(a), e.nombre(b)}

    async def test_no_a_quien_ya_empezo_su_partido(self, e):
        torneo = await e.torneo()
        a, b, c, d = [await e.inscrito(torneo) for _ in range(4)]
        ronda = await e.sesion(torneo)
        await e.partido(ronda, a, b, empezado=True)
        await e.partido(ronda, c, d)

        await e.caso(_hora_de_madrid(9)).execute()

        assert e.preguntados() == {e.nombre(c), e.nombre(d)}

    async def test_no_a_quien_tiene_handicap_personalizado(self, e):
        torneo = await e.torneo()
        propio = await e.inscrito(torneo, personalizado=Decimal("8.0"))
        otro = await e.inscrito(torneo)
        await e.sesion(torneo)

        await e.caso(_hora_de_madrid(3)).execute()

        assert e.preguntados() == {e.nombre(otro)}
        assert propio not in await e.uow.handicap_refreshes.del_dia(torneo, SABADO)

    async def test_sin_licencia_espanola_no_se_pregunta_pero_queda_apuntado(self, e):
        torneo = await e.torneo()
        frances = await e.inscrito(torneo, pais="FR")
        await e.sesion(torneo)

        await e.caso(_hora_de_madrid(3)).execute()

        assert e.preguntados() == set()
        assert (await e.uow.handicap_refreshes.del_dia(torneo, SABADO))[frances] is (
            ResultadoRefresco.SIN_LICENCIA_ESPANOLA
        )

    async def test_quien_juega_dos_torneos_hoy_se_pregunta_una_vez(self, e):
        primero, segundo = await e.torneo(), await e.torneo()
        jugador = e.usuarios.alta()
        for torneo in (primero, segundo):
            await create_approved_enrollment(e.uow, torneo.value, jugador)
            await e.sesion(torneo)

        await e.caso(_hora_de_madrid(3)).execute()

        assert e.rfeg.search_handicap.await_count == 1
        for torneo in (primero, segundo):
            assert (await e.uow.handicap_refreshes.del_dia(torneo, SABADO))[jugador] is (
                ResultadoRefresco.ACTUALIZADO
            )


class TestComo:
    async def test_uno_a_uno_con_pausa_entre_consultas(self, e):
        torneo = await e.torneo()
        # El creador queda inscrito al crearla: con dos más son tres jugadores
        for _ in range(2):
            await e.inscrito(torneo)
        await e.sesion(torneo)

        await e.caso(_hora_de_madrid(3)).execute()

        assert e.esperas == [PAUSA_ENTRE_CONSULTAS, PAUSA_ENTRE_CONSULTAS]

    async def test_una_segunda_vuelta_no_repite_a_nadie(self, e):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo)

        await e.caso(_hora_de_madrid(3)).execute()
        await e.caso(_hora_de_madrid(3, 15)).execute()

        assert e.rfeg.search_handicap.await_count == 1

    async def test_lo_fallido_se_reintenta_hasta_las_siete(self, e):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo)
        e.rfeg.search_handicap = AsyncMock(side_effect=ConnectionError("RFEG caída"))

        await e.caso(_hora_de_madrid(3)).execute()
        await e.caso(_hora_de_madrid(6, 45)).execute()
        await e.caso(_hora_de_madrid(7)).execute()

        assert e.rfeg.search_handicap.await_count == 2

    async def test_lo_que_no_encuentra_no_se_reintenta(self, e):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo)
        e.rfeg.search_handicap = AsyncMock(return_value=None)

        await e.caso(_hora_de_madrid(3)).execute()
        await e.caso(_hora_de_madrid(3, 15)).execute()

        assert e.rfeg.search_handicap.await_count == 1

    async def test_un_jugador_que_ya_no_existe_no_para_a_los_demas(self, e):
        torneo = await e.torneo()
        borrado = await e.inscrito(torneo)
        otro = await e.inscrito(torneo)
        await e.sesion(torneo)
        del e.usuarios.por_id[borrado]

        await e.caso(_hora_de_madrid(3)).execute()

        assert e.preguntados() == {e.nombre(otro)}
        assert (await e.uow.handicap_refreshes.del_dia(torneo, SABADO))[borrado] is (
            ResultadoRefresco.NO_ENCONTRADO
        )


class TestLoQueEncontroLaRevision:
    """Hallazgos de /code-review en la 502a."""

    async def test_un_fallo_inesperado_queda_apuntado_y_no_se_repite_tras_las_siete(self, e):
        torneo = await e.torneo()
        jugador = await e.inscrito(torneo)
        await e.sesion(torneo)
        lecturas = []

        async def explota(user_id):
            lecturas.append(user_id)
            raise RuntimeError("la sesión se quedó a medias")

        e.usuarios.find_by_id = explota

        await e.caso(_hora_de_madrid(3)).execute()
        await e.caso(_hora_de_madrid(7, 30)).execute()

        assert (await e.uow.handicap_refreshes.del_dia(torneo, SABADO))[jugador] is (
            ResultadoRefresco.FALLIDO
        )
        assert lecturas.count(jugador) == 1

    async def test_la_rfeg_se_consulta_sin_ninguna_transaccion_abierta(self, e):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo)
        abiertas_al_preguntar = []

        async def rfeg(_nombre):
            abiertas_al_preguntar.append(e.uow.abiertas)
            return 11.2

        e.rfeg.search_handicap = rfeg

        await e.caso(_hora_de_madrid(3)).execute()

        assert abiertas_al_preguntar and set(abiertas_al_preguntar) == {0}

    async def test_cada_jugador_con_sus_propias_herramientas(self, e):
        torneo = await e.torneo()
        await e.inscrito(torneo)
        await e.sesion(torneo)

        await e.caso(_hora_de_madrid(3)).execute()

        # Una para buscar a quién preguntar, una por cada uno de los dos jugadores
        # y una para recalcular los partidos de ese torneo y día
        assert e.herramientas_pedidas == 4

    async def test_si_la_primera_sesion_no_tiene_zona_vale_la_de_otra(self, e):
        torneo = await e.torneo()
        jugador = await e.inscrito(torneo)
        sin_zona, con_zona = await e.sesion(torneo), await e.sesion(torneo)
        zonas = {sin_zona.golf_course_id: None, con_zona.golf_course_id: "Europe/Madrid"}
        e.zona.for_course = AsyncMock(side_effect=lambda campo: zonas[campo])

        await e.caso(_hora_de_madrid(3)).execute()

        assert e.nombre(jugador) in e.preguntados()


class TestRecalcularLosPartidosDeHoy:
    """Los partidos de hoy sin empezar se recalculan con el hándicap nuevo (502b)."""

    async def _torneo_con_handicap(self, e) -> CompetitionId:
        from src.modules.competition.application.dto.competition_dto import (
            CreateCompetitionRequestDTO,
        )
        from src.modules.competition.application.use_cases.create_competition_use_case import (
            CreateCompetitionUseCase,
        )
        from src.modules.competition.domain.services.location_builder import LocationBuilder
        from tests.unit.modules.competition.application.use_cases.helpers import (
            USUARIOS_CON_GENERO,
        )

        respuesta = await CreateCompetitionUseCase(
            e.uow, LocationBuilder(e.uow.countries), USUARIOS_CON_GENERO
        ).execute(
            CreateCompetitionRequestDTO(
                name="Ryder con hándicap",
                start_date=SABADO,
                end_date=SABADO,
                main_country="ES",
                play_mode="HANDICAP",
            ),
            UserId.generate(),
        )
        return CompetitionId(respuesta.id)

    async def _partido_de_hoy(self, e, empezado=False, dia=SABADO):
        torneo = await self._torneo_con_handicap(e)
        a, b = await e.inscrito(torneo), await e.inscrito(torneo)
        e.usuarios.con_handicap(a, 20.0)
        e.usuarios.con_handicap(b, 4.0)
        partido = await e.partido(await e.sesion(torneo, dia=dia), a, b, empezado=empezado)
        return partido, a

    async def test_un_partido_de_hoy_sin_empezar_se_recalcula_sobre_el_mismo(self, e):
        partido, a = await self._partido_de_hoy(e)
        e.rfeg.search_handicap = AsyncMock(return_value=8.0)

        await e.caso(_hora_de_madrid(3)).execute()

        recalculado = await e.uow.matches.find_by_id(partido.id)
        assert recalculado is not None
        jugador_a = recalculado.team_a_players[0]
        assert jugador_a.user_id == a
        assert jugador_a.playing_handicap != 10  # el de la generación de mentira

    async def test_un_partido_empezado_no_se_toca(self, e):
        partido, _ = await self._partido_de_hoy(e, empezado=True)
        antes = partido.team_a_players

        await e.caso(_hora_de_madrid(9)).execute()

        assert (await e.uow.matches.find_by_id(partido.id)).team_a_players == antes

    async def test_si_nadie_se_actualiza_no_se_toca(self, e):
        partido, _ = await self._partido_de_hoy(e)
        antes = partido.team_a_players
        e.rfeg.search_handicap = AsyncMock(return_value=None)

        await e.caso(_hora_de_madrid(3)).execute()

        assert (await e.uow.matches.find_by_id(partido.id)).team_a_players == antes

    async def test_si_la_rfeg_falla_no_se_toca(self, e):
        partido, _ = await self._partido_de_hoy(e)
        antes = partido.team_a_players
        e.rfeg.search_handicap = AsyncMock(side_effect=ConnectionError("RFEG caída"))

        await e.caso(_hora_de_madrid(3)).execute()

        assert (await e.uow.matches.find_by_id(partido.id)).team_a_players == antes

    async def test_un_partido_que_empieza_durante_el_refresco_no_impide_los_demas(self, e):
        """Carrera: el partido empieza mientras se pregunta a la RFEG por sus jugadores."""
        torneo = await self._torneo_con_handicap(e)
        a, b, c, d = [await e.inscrito(torneo) for _ in range(4)]
        sesion = await e.sesion(torneo)
        se_adelanta = await e.partido(sesion, a, b)
        sin_empezar = await e.partido(sesion, c, d)
        antes = se_adelanta.team_a_players

        async def rfeg(_nombre):
            if se_adelanta.status.value == "SCHEDULED":
                se_adelanta.start()
            return 8.0

        e.rfeg.search_handicap = rfeg

        await e.caso(_hora_de_madrid(3)).execute()

        assert (await e.uow.matches.find_by_id(se_adelanta.id)).team_a_players == antes
        recalculado = await e.uow.matches.find_by_id(sin_empezar.id)
        assert recalculado.team_a_players[0].playing_handicap != 10

    async def test_un_partido_que_no_se_puede_recalcular_no_impide_los_demas(self, e):
        """Revisión: un jugador dado de baja tras generarse su partido no para el resto."""
        torneo = await self._torneo_con_handicap(e)
        a, b, c, d = [await e.inscrito(torneo) for _ in range(4)]
        sesion = await e.sesion(torneo)
        con_baja = await e.partido(sesion, a, b)
        sin_problema = await e.partido(sesion, c, d)
        antes = con_baja.team_a_players
        async with e.uow:
            inscripcion = next(
                i
                for i in await e.uow.enrollments.find_by_competition_and_status(
                    torneo, EnrollmentStatus.APPROVED
                )
                if i.user_id == b
            )
            inscripcion.withdraw()
            await e.uow.enrollments.update(inscripcion)
        e.rfeg.search_handicap = AsyncMock(return_value=8.0)

        await e.caso(_hora_de_madrid(3)).execute()

        assert (await e.uow.matches.find_by_id(con_baja.id)).team_a_players == antes
        recalculado = await e.uow.matches.find_by_id(sin_problema.id)
        assert recalculado.team_a_players[0].playing_handicap != 10


class TestLoQueEncontroLaRevisionDeLa502b:
    """Hallazgos de /code-review en el recálculo de los partidos."""

    async def test_si_el_recalculo_falla_se_hace_en_la_vuelta_siguiente(self, e):
        partido, _ = await TestRecalcularLosPartidosDeHoy()._partido_de_hoy(e)
        e.rfeg.search_handicap = AsyncMock(return_value=8.0)
        e.campos.find_by_id = AsyncMock(side_effect=RuntimeError("se cortó el proceso"))

        await e.caso(_hora_de_madrid(3)).execute()
        assert (await e.uow.matches.find_by_id(partido.id)).team_a_players[0].playing_handicap == 10

        e.campos.find_by_id = AsyncMock(return_value=_campo())
        await e.caso(_hora_de_madrid(3, 15)).execute()

        recalculado = await e.uow.matches.find_by_id(partido.id)
        assert recalculado.team_a_players[0].playing_handicap != 10
        # Sin volver a preguntar a la RFEG: ya estaba apuntado
        assert e.rfeg.search_handicap.await_count == 2  # sus dos jugadores, una vez

    async def test_si_los_golpes_no_cambian_el_partido_no_se_reescribe(self, e):
        partido, _ = await TestRecalcularLosPartidosDeHoy()._partido_de_hoy(e)
        e.rfeg.search_handicap = AsyncMock(return_value=8.0)
        await e.caso(_hora_de_madrid(3)).execute()
        recalculado = await e.uow.matches.find_by_id(partido.id)
        escrito = recalculado.updated_at

        await e.caso(_hora_de_madrid(3, 15)).execute()

        assert (await e.uow.matches.find_by_id(partido.id)).updated_at == escrito

    async def test_cada_partido_en_su_propio_savepoint(self, e):
        torneo = await TestRecalcularLosPartidosDeHoy()._torneo_con_handicap(e)
        a, b, c, d = [await e.inscrito(torneo) for _ in range(4)]
        sesion = await e.sesion(torneo)
        await e.partido(sesion, a, b)
        await e.partido(sesion, c, d)
        e.rfeg.search_handicap = AsyncMock(return_value=8.0)

        await e.caso(_hora_de_madrid(3)).execute()

        assert e.uow.savepoints == 2
