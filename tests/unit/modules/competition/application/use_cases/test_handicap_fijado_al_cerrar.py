"""
El hándicap de cada jugador se fija al cerrar las inscripciones de un stroke play (#251).

Decidido con Agustín el 7 oct 2026, como hace la RFEG: al cerrar se guarda en
cada inscripción el hándicap que cuenta (el personalizado o el del perfil), y es
el de todo el torneo. Iniciar, o arrancar con el primer golpe, ya no lo toca.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    CreateCompetitionRequestDTO,
    StartCompetitionRequestDTO,
)
from src.modules.competition.application.services.handicaps_al_cerrar import (
    PlayersWithoutHandicapError,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    create_approved_enrollment,
    plaza_para_todos,
)

pytestmark = pytest.mark.asyncio


class _Usuarios:
    def __init__(self):
        self.handicaps: dict[UserId, float | None] = {}

    def _usuario(self, user_id):
        h = self.handicaps.get(user_id)
        u = MagicMock()
        u.id = user_id
        u.handicap = None if h is None else MagicMock(value=h)
        u.get_full_name.return_value = f"Nombre {str(user_id)[:4]}"
        u.get_public_name.return_value = f"Nombre {str(user_id)[:4]}"
        u.display_name_or_legal.return_value = f"Nombre {str(user_id)[:4]}"
        u.first_name = "Nombre"
        u.last_name = str(user_id)[:4]
        return u

    async def find_by_ids(self, ids):
        return [self._usuario(i) for i in ids if i in self.handicaps]

    async def find_by_id(self, user_id):
        return self._usuario(user_id) if user_id in self.handicaps else None


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.usuarios = _Usuarios()
        self.creador = UserId(uuid4())
        self.usuarios.handicaps[self.creador] = 10.0

    async def torneo(
        self, tipo="STABLEFORD", limites=("12.0", "26.0"), contador=None
    ) -> CompetitionId:
        extra = {"tournament_type": tipo}
        if tipo != "RYDER_CUP":
            extra["stroke_play"] = (
                {"category_count": contador}
                if contador
                else {"category_limits": [Decimal(v) for v in limites]}
            )
        respuesta = await CreateCompetitionUseCase(
            self.uow, LocationBuilder(self.uow.countries), USUARIOS_CON_GENERO
        ).execute(
            CreateCompetitionRequestDTO(
                name="Medal de octubre",
                start_date=date(2030, 10, 12),
                end_date=date(2030, 10, 12),
                main_country="ES",
                play_mode="HANDICAP",
                **extra,
            ),
            self.creador,
        )
        torneo = CompetitionId(respuesta.id)
        ronda = Round.create(
            competition_id=torneo,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2030, 10, 12),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with self.uow:
            await self.uow.rounds.add(ronda)
        return torneo

    async def jugador(self, torneo, handicap: float | None, personalizado=None) -> UserId:
        user_id = UserId(uuid4())
        self.usuarios.handicaps[user_id] = handicap
        await create_approved_enrollment(self.uow, torneo.value, user_id, personalizado)
        return user_id

    async def cerrar(self, torneo):
        # Sin franja no se cierra un stroke play (#251, 8 oct 2026)
        await plaza_para_todos(self.uow, torneo)
        return await CloseEnrollmentsUseCase(self.uow, self.usuarios).execute(
            CloseEnrollmentsRequestDTO(competition_id=torneo.value), self.creador
        )

    async def iniciar(self, torneo):
        return await StartCompetitionUseCase(self.uow, self.usuarios).execute(
            StartCompetitionRequestDTO(competition_id=torneo.value), self.creador
        )

    async def inscripciones(self, torneo) -> dict:
        return {
            e.user_id: e
            for e in await self.uow.enrollments.find_by_competition_and_status(
                torneo, EnrollmentStatus.APPROVED
            )
        }

    async def estado(self, torneo):
        return (await self.uow.competitions.find_by_id(torneo)).status


@pytest.fixture
def e():
    return _Escenario()


class TestAlCerrarInscripciones:
    async def test_se_fija_el_handicap_que_cuenta_de_cada_uno(self, e):
        torneo = await e.torneo()
        del_perfil = await e.jugador(torneo, 14.2)
        propio = await e.jugador(torneo, 30.0, personalizado=Decimal("8.0"))

        await e.cerrar(torneo)

        inscripciones = await e.inscripciones(torneo)
        assert inscripciones[del_perfil].fixed_handicap == Decimal("14.2")
        assert inscripciones[propio].fixed_handicap == Decimal("8.0")
        assert await e.estado(torneo) is CompetitionStatus.CLOSED

    async def test_si_aun_asi_falta_alguno_no_se_cierra_y_se_dice_quien(self, e):
        """Red: con las reglas de inscripción no debería llegar nadie sin hándicap."""
        torneo = await e.torneo()
        sin = await e.jugador(torneo, None)

        with pytest.raises(PlayersWithoutHandicapError) as error:
            await e.cerrar(torneo)

        assert [j.user_id for j in error.value.players] == [sin]
        assert await e.estado(torneo) is CompetitionStatus.ACTIVE

    async def test_cerrar_una_competicion_que_ya_no_se_puede_cerrar_dice_por_que(self, e):
        """Primero el estado: pedir hándicaps para algo imposible no ayuda (/code-review)."""
        torneo = await e.torneo()
        await e.cerrar(torneo)
        await e.jugador(torneo, None)

        with pytest.raises(CompetitionStateError):
            await e.cerrar(torneo)

    async def test_una_ryder_se_cierra_como_siempre_y_no_fija_nada(self, e):
        torneo = await e.torneo(tipo="RYDER_CUP")
        sin = await e.jugador(torneo, None)

        await e.cerrar(torneo)

        assert await e.estado(torneo) is CompetitionStatus.CLOSED
        assert (await e.inscripciones(torneo))[sin].fixed_handicap is None

    async def test_al_reabrir_y_volver_a_cerrar_se_fija_de_nuevo(self, e):
        torneo = await e.torneo()
        jugador = await e.jugador(torneo, 14.2)
        await e.cerrar(torneo)
        async with e.uow:
            competicion = await e.uow.competitions.find_by_id(torneo)
            competicion.reopen_enrollments()
            await e.uow.competitions.update(competicion)
        e.usuarios.handicaps[jugador] = 13.1

        await e.cerrar(torneo)

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("13.1")


class TestAlIniciar:
    async def test_no_se_vuelve_a_fijar_ni_a_exigir(self, e):
        torneo = await e.torneo()
        jugador = await e.jugador(torneo, 14.2)
        await e.cerrar(torneo)
        # Ni aunque luego le cambie el hándicap del perfil: el de todo el torneo es el del cierre
        e.usuarios.handicaps[jugador] = 2.0

        await e.iniciar(torneo)

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("14.2")
        assert await e.estado(torneo) is CompetitionStatus.IN_PROGRESS

    async def test_tampoco_al_arrancar_con_el_primer_golpe(self, e):
        torneo = await e.torneo()
        jugador = await e.jugador(torneo, 14.2)
        await e.cerrar(torneo)
        e.usuarios.handicaps[jugador] = 2.0
        caso = SubmitHoleScoreUseCase(e.uow, e.usuarios, scoring_service=MagicMock())

        async with e.uow:
            await caso._arranca_la_competicion(torneo, ValueError("no se puede"))

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("14.2")

    async def test_se_lee_la_competicion_bloqueada(self, e):
        torneo = await e.torneo()
        await e.cerrar(torneo)

        async def sin_bloquear(_id):
            raise AssertionError("Iniciar lee la competición bloqueada")

        e.uow.competitions.find_by_id = sin_bloquear

        await e.iniciar(torneo)


class TestEditarLaCompeticion:
    async def test_se_lee_bloqueada(self, e):
        """Mover las fechas no puede cruzarse con un cambio de las jornadas por jugador."""
        from src.modules.competition.application.dto.competition_dto import (
            UpdateCompetitionRequestDTO,
        )
        from src.modules.competition.application.use_cases.update_competition_use_case import (
            UpdateCompetitionUseCase,
        )

        torneo = await e.torneo()

        async def sin_bloquear(_id):
            raise AssertionError("Editar lee la competición bloqueada")

        e.uow.competitions.find_by_id = sin_bloquear
        campos = MagicMock()
        campos.find_by_ids = AsyncMock(return_value=[])

        await UpdateCompetitionUseCase(e.uow, LocationBuilder(e.uow.countries), campos).execute(
            torneo, UpdateCompetitionRequestDTO(name="Medal de noviembre"), e.creador
        )


class TestLaListaDeInscritos:
    """Hándicap fijado y categoría, solo con el hándicap ya fijado (al cerrar) y con la regla de los seis."""

    async def _lista(self, e, torneo):
        from src.modules.competition.application.use_cases.list_enrollments_use_case import (
            ListEnrollmentsUseCase,
        )

        return await ListEnrollmentsUseCase(e.uow).execute_con_categorias(str(torneo.value))

    async def test_antes_de_cerrar_no_hay_categorias(self, e):
        torneo = await e.torneo()
        await e.jugador(torneo, 14.2)

        _, categorias = await self._lista(e, torneo)

        assert categorias == {}

    async def test_al_cerrar_con_la_regla_de_los_seis(self, e):
        torneo = await e.torneo(limites=("12.0",))
        bajos = [await e.jugador(torneo, 5.0) for _ in range(5)]  # con el creador (10,0), 6
        altos = [await e.jugador(torneo, 20.0) for _ in range(6)]
        await e.cerrar(torneo)

        _, categorias = await self._lista(e, torneo)

        assert {categorias[u] for u in bajos} == {1}
        assert {categorias[u] for u in altos} == {2}

    async def test_con_pocos_en_una_se_juntan(self, e):
        torneo = await e.torneo(limites=("12.0",))
        alto = await e.jugador(torneo, 20.0)
        await e.cerrar(torneo)

        _, categorias = await self._lista(e, torneo)

        assert categorias[alto] == 1

    async def test_en_una_ryder_no_hay_categorias(self, e):
        torneo = await e.torneo(tipo="RYDER_CUP")
        await e.jugador(torneo, 14.2)
        await e.cerrar(torneo)

        _, categorias = await self._lista(e, torneo)

        assert categorias == {}


class TestLoQueEncontroCodeReviewEnLaPR2:
    async def test_devolver_a_cerrada_una_en_juego_no_vuelve_a_fijar(self, e):
        torneo = await e.torneo()
        jugador = await e.jugador(torneo, 14.2)
        await e.cerrar(torneo)
        await e.iniciar(torneo)
        e.usuarios.handicaps[jugador] = 2.0

        # El mismo botón de cerrar sirve para volver atrás desde EN JUEGO
        await e.cerrar(torneo)

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("14.2")

    async def test_la_categoria_se_fija_al_cerrar_y_no_se_mueve_si_alguien_se_retira(self, e):
        torneo = await e.torneo(limites=("12.0",))
        bajos = [await e.jugador(torneo, 5.0) for _ in range(5)]  # con el creador, 6
        altos = [await e.jugador(torneo, 20.0) for _ in range(6)]
        await e.cerrar(torneo)
        async with e.uow:
            retirado = (await e.inscripciones(torneo))[altos[0]]
            retirado.withdraw()
            await e.uow.enrollments.update(retirado)

        inscripciones = await e.inscripciones(torneo)

        assert {inscripciones[u].fixed_category for u in bajos} == {1}
        assert {inscripciones[u].fixed_category for u in altos[1:]} == {2}

    async def test_no_se_aprueba_una_solicitud_despues_de_cerrar(self, e):
        from src.modules.competition.application.dto.enrollment_dto import (
            HandleEnrollmentRequestDTO,
        )
        from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
            HandleEnrollmentUseCase,
        )
        from src.modules.competition.domain.entities.enrollment import (
            Enrollment,
            EnrollmentStateError,
        )
        from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId

        torneo = await e.torneo()
        pide = UserId(uuid4())
        e.usuarios.handicaps[pide] = 14.2
        solicitud = Enrollment.request(
            id=EnrollmentId.generate(), competition_id=torneo, user_id=pide
        )
        async with e.uow:
            await e.uow.enrollments.add(solicitud)
        await e.cerrar(torneo)

        with pytest.raises(EnrollmentStateError, match="cerradas"):
            await HandleEnrollmentUseCase(e.uow, e.usuarios).execute(
                HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
                e.creador,
            )


class TestCategoriasIgualesAlCerrar:
    """N categorías iguales: los límites salen al cerrar (decidido el 10 oct 2026)."""

    async def _doce(self, e, torneo):
        """Con el creador (10,0), doce: 1-5, 10 y 20-25."""
        bajos = [await e.jugador(torneo, float(h)) for h in range(1, 6)]
        altos = [await e.jugador(torneo, float(h)) for h in range(20, 26)]
        return bajos, altos

    async def _limites(self, e, torneo):
        return (await e.uow.competitions.find_by_id(torneo)).stroke_play.category_limits

    async def test_al_cerrar_se_reparten_y_se_fija_la_categoria(self, e):
        torneo = await e.torneo(contador=2)
        bajos, altos = await self._doce(e, torneo)

        await e.cerrar(torneo)

        assert await self._limites(e, torneo) == (Decimal("10.0"),)
        inscripciones = await e.inscripciones(torneo)
        assert {inscripciones[u].fixed_category for u in [*bajos, e.creador]} == {1}
        assert {inscripciones[u].fixed_category for u in altos} == {2}

    async def test_reabrir_y_volver_a_cerrar_reparte_con_los_de_ahora(self, e):
        torneo = await e.torneo(contador=2)
        await self._doce(e, torneo)
        await e.cerrar(torneo)
        async with e.uow:
            competicion = await e.uow.competitions.find_by_id(torneo)
            competicion.reopen_enrollments()
            await e.uow.competitions.update(competicion)
        assert await self._limites(e, torneo) == ()
        for _ in range(12):
            await e.jugador(torneo, 40.0)

        await e.cerrar(torneo)

        # 24: el 12.º es el 25,0
        assert await self._limites(e, torneo) == (Decimal("25.0"),)

    async def test_volver_a_cerrada_desde_en_juego_no_reparte(self, e):
        torneo = await e.torneo(contador=2)
        await self._doce(e, torneo)
        await e.cerrar(torneo)
        await e.iniciar(torneo)
        for _ in range(12):
            await e.jugador(torneo, 40.0)

        await e.cerrar(torneo)

        assert await self._limites(e, torneo) == (Decimal("10.0"),)

    async def test_la_rfeg_tras_el_cierre_no_mueve_los_limites_y_recoloca(self, e):
        from src.modules.competition.application.services.handicaps_al_cerrar import (
            HandicapsAlCerrar,
        )

        torneo = await e.torneo(contador=2)
        bajos, _ = await self._doce(e, torneo)
        # Uno más abajo: al subir uno, la 1.ª se queda con seis y no se junta
        await e.jugador(torneo, 6.0)
        await e.cerrar(torneo)
        altos_antes = 6

        async with e.uow:
            competicion = await e.uow.competitions.find_by_id(torneo)
            await HandicapsAlCerrar(e.uow, e.usuarios).corregir(
                competicion, bajos[0], Decimal("30.0")
            )

        assert await self._limites(e, torneo) == (Decimal("10.0"),)
        inscripciones = await e.inscripciones(torneo)
        assert inscripciones[bajos[0]].fixed_category == 2
        assert sum(1 for i in inscripciones.values() if i.fixed_category == 2) == altos_antes + 1

    async def test_y_luego_la_regla_de_los_seis(self, e):
        # Cuatro con el creador, en 2: dos y dos, que se juntan en una
        torneo = await e.torneo(contador=2)
        for h in (4.0, 20.0, 22.0):
            await e.jugador(torneo, h)

        await e.cerrar(torneo)

        assert await self._limites(e, torneo) == (Decimal("10.0"),)
        assert {i.fixed_category for i in (await e.inscripciones(torneo)).values()} == {1}

    async def test_a_mano_se_cierra_como_siempre(self, e):
        torneo = await e.torneo(limites=("12.0",))
        await self._doce(e, torneo)

        await e.cerrar(torneo)

        assert await self._limites(e, torneo) == (Decimal("12.0"),)


class TestHandicapsConDosDecimales:
    """
    Un perfil puede traer dos decimales (el manual solo mira el rango) y la
    columna fijada guarda uno: se fija redondeado, y reparto y categoría salen
    de ese mismo valor (revisor de la PR de categorías iguales, 10 oct 2026).
    """

    async def test_con_categorias_iguales_se_cierra_y_el_limite_lleva_un_decimal(self, e):
        torneo = await e.torneo(contador=2)
        for h in (1.0, 2.0, 3.0, 4.0, 6.05):
            await e.jugador(torneo, h)
        for h in range(20, 26):
            await e.jugador(torneo, float(h))

        await e.cerrar(torneo)

        competicion = await e.uow.competitions.find_by_id(torneo)
        # Doce con el creador (10,0): el 6.º es el 10,0; el 6,05 queda en 6,1
        assert competicion.stroke_play.category_limits == (Decimal("10.0"),)
        assert {i.fixed_handicap for i in (await e.inscripciones(torneo)).values()} >= {
            Decimal("6.1")
        }

    async def test_el_limite_calculado_sale_del_valor_redondeado(self, e):
        torneo = await e.torneo(contador=2)
        for h in (1.0, 2.0, 3.0, 4.0, 5.0):
            await e.jugador(torneo, h)
        frontera = await e.jugador(torneo, 9.96)  # con el creador (10,0), dos «10,0»
        for h in range(20, 25):
            await e.jugador(torneo, float(h))

        await e.cerrar(torneo)

        competicion = await e.uow.competitions.find_by_id(torneo)
        assert competicion.stroke_play.category_limits == (Decimal("10.0"),)
        assert (await e.inscripciones(torneo))[frontera].fixed_handicap == Decimal("10.0")

    async def test_a_mano_la_categoria_es_la_del_handicap_fijado(self, e):
        # 12,04 se fija como 12,0: con «hasta 12,0», 1.ª; no 2.ª por los centésimos
        torneo = await e.torneo(limites=("12.0",))
        justo = await e.jugador(torneo, 12.04)
        for _ in range(4):
            await e.jugador(torneo, 5.0)
        for _ in range(6):
            await e.jugador(torneo, 20.0)

        await e.cerrar(torneo)

        suya = (await e.inscripciones(torneo))[justo]
        assert (suya.fixed_handicap, suya.fixed_category) == (Decimal("12.0"), 1)

    async def test_la_correccion_de_la_rfeg_tambien_se_redondea(self, e):
        from src.modules.competition.application.services.handicaps_al_cerrar import (
            HandicapsAlCerrar,
        )

        torneo = await e.torneo(limites=("12.0",))
        jugador = await e.jugador(torneo, 5.0)
        await e.cerrar(torneo)

        async with e.uow:
            competicion = await e.uow.competitions.find_by_id(torneo)
            await HandicapsAlCerrar(e.uow, e.usuarios).corregir(
                competicion, jugador, Decimal("12.04")
            )

        assert (await e.inscripciones(torneo))[jugador].fixed_handicap == Decimal("12.0")

    async def test_un_plus_se_redondea_hacia_fuera_como_postgres(self, e):
        torneo = await e.torneo(limites=("12.0",))
        plus = await e.jugador(torneo, -0.05)

        await e.cerrar(torneo)

        assert (await e.inscripciones(torneo))[plus].fixed_handicap == Decimal("-0.1")
