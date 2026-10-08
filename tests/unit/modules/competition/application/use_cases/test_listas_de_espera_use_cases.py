"""
Las listas de espera de las franjas, de punta a punta (#251, 20 sep y 8 oct 2026).

| Caso                                                   | Resultado                                  |
|--------------------------------------------------------|--------------------------------------------|
| Esperar en una llena                                   | En la lista, por orden de llegada          |
| Esperar en una con sitio                               | 400: que coja plaza                        |
| Esperar con las inscripciones cerradas                 | 400                                        |
| Esperar por otro                                       | 403                                        |
| Alguien suelta su plaza                                | El primero la recibe (desde la lista)      |
| Alguien se cambia a otra franja                        | La que deja se rellena                     |
| Alguien se retira                                      | Se rellena; y él sale de las listas        |
| Ampliar la franja                                      | Se rellena con los que quepan              |
| El primero ya juega ese día (cogió otra)               | Se le salta: le toca al siguiente          |
| Al conseguir plaza                                     | Sale de las listas de ese día              |
| Al llenar el cupo de jornadas                          | Sale de todas                              |
| Al cerrar las inscripciones                            | Las listas se vacían, y ya no se rellena   |
| Dejar de esperar                                       | Fuera de la lista                          |
| «Requiere tu atención»                                 | La plaza asignada, hasta «Entendido»       |
"""

from datetime import date, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import WithdrawEnrollmentRequestDTO
from src.modules.competition.application.dto.round_match_dto import (
    TeeSheetDTO,
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    PlazaEnFranjaError,
)
from src.modules.competition.application.use_cases.listas_de_espera_use_case import (
    DejarDeEsperarUseCase,
    EntendidoUseCase,
    EsperarUseCase,
    MisPlazasAsignadasUseCase,
)
from src.modules.competition.application.use_cases.plazas_en_franjas_use_case import (
    CogerPlazaUseCase,
    SoltarPlazaUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

VIERNES = date(2030, 10, 11)
SABADO = VIERNES + timedelta(days=1)


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.creador = UserId(uuid4())

    async def torneo(self, jornadas=1):
        self.competicion = Competition(
            id=CompetitionId(uuid4()),
            creator_id=self.creador,
            name=CompetitionName("Medal de octubre"),
            dates=DateRange(VIERNES, SABADO),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            tournament_type=TournamentType.STABLEFORD,
            status=CompetitionStatus.ACTIVE,
            category_limits=[Decimal("12.0")],
            max_matchdays_per_player=jornadas,
        )
        # De una sola salida de 3: cupo 3
        self.manana = self._franja(VIERNES, SessionType.MORNING, time(9, 0))
        self.tarde = self._franja(VIERNES, SessionType.AFTERNOON, time(15, 0))
        self.sabado = self._franja(SABADO, SessionType.MORNING, time(9, 0))
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
            for f in (self.manana, self.tarde, self.sabado):
                await self.uow.rounds.add(f)

    def _franja(self, dia, sesion, hora):
        return Round.create_franja(
            competition_id=self.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=dia,
            session_type=sesion,
            hoja_de_salidas=HojaDeSalidas(hora, hora, 10, 3),
        )

    async def aprobado(self) -> UserId:
        user_id = UserId(uuid4())
        async with self.uow:
            await self.uow.enrollments.add(
                Enrollment.direct_enroll(
                    id=EnrollmentId.generate(), competition_id=self.competicion.id, user_id=user_id
                )
            )
        return user_id

    async def llena(self, franja) -> list[UserId]:
        dentro = [await self.aprobado() for _ in range(3)]
        for j in dentro:
            await self.coger(franja, j)
        return dentro

    async def coger(self, franja, jugador, en_lugar_de=None):
        await CogerPlazaUseCase(self.uow).execute(
            franja.id, jugador, jugador, en_lugar_de=en_lugar_de
        )

    async def soltar(self, franja, jugador):
        await SoltarPlazaUseCase(self.uow).execute(franja.id, jugador, jugador)

    async def esperar(self, franja, jugador, quien=None):
        await EsperarUseCase(self.uow).execute(franja.id, jugador, quien or jugador)

    async def plazas(self, franja):
        return [
            p.user_id
            for p in await self.uow.plazas.de_la_competicion(self.competicion.id)
            if p.round_id == franja.id
        ]

    async def espera(self, franja):
        return [
            e.user_id
            for e in await self.uow.esperas.de_la_competicion(self.competicion.id)
            if e.round_id == franja.id
        ]

    async def cambiar_estado(self, status):
        self.competicion._status = status
        async with self.uow:
            await self.uow.competitions.update(self.competicion)


@pytest.fixture
def e():
    return _Escenario()


class TestEsperar:
    async def test_en_una_llena_por_orden_de_llegada(self, e):
        await e.torneo()
        await e.llena(e.manana)
        primero, segundo = await e.aprobado(), await e.aprobado()

        await e.esperar(e.manana, primero)
        await e.esperar(e.manana, segundo)

        assert await e.espera(e.manana) == [primero, segundo]

    async def test_en_una_con_sitio_no(self, e):
        await e.torneo()

        with pytest.raises(PlazaEnFranjaError, match="sitio"):
            await e.esperar(e.manana, await e.aprobado())

    async def test_con_las_inscripciones_cerradas_no(self, e):
        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()
        await e.cambiar_estado(CompetitionStatus.CLOSED)

        with pytest.raises(PlazaEnFranjaError, match="cerrar"):
            await e.esperar(e.manana, jugador)

    async def test_por_otro_no(self, e):
        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()

        with pytest.raises(NotCompetitionCreatorError):
            await e.esperar(e.manana, jugador, quien=UserId(uuid4()))

    async def test_sin_estar_aprobado_no(self, e):
        await e.torneo()
        await e.llena(e.manana)

        with pytest.raises(PlazaEnFranjaError, match="aprobados"):
            await e.esperar(e.manana, UserId(uuid4()))

    async def test_un_jugador_no_saca_a_otro_de_la_lista(self, e):
        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()
        await e.esperar(e.manana, jugador)

        with pytest.raises(NotCompetitionCreatorError):
            await DejarDeEsperarUseCase(e.uow).execute(e.manana.id, jugador, UserId(uuid4()))

    async def test_dejar_de_esperar(self, e):
        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()
        await e.esperar(e.manana, jugador)

        await DejarDeEsperarUseCase(e.uow).execute(e.manana.id, jugador, jugador)

        assert await e.espera(e.manana) == []


class TestSeRellenaSola:
    async def test_alguien_suelta_y_el_primero_la_recibe(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        primero, segundo = await e.aprobado(), await e.aprobado()
        await e.esperar(e.manana, primero)
        await e.esperar(e.manana, segundo)

        await e.soltar(e.manana, dentro[0])

        assert primero in await e.plazas(e.manana)
        assert await e.espera(e.manana) == [segundo]

    async def test_alguien_se_cambia_y_la_que_deja_se_rellena(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)

        await e.coger(e.tarde, dentro[0], en_lugar_de=e.manana.id)

        assert espera in await e.plazas(e.manana)

    async def test_alguien_se_retira_y_se_rellena(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)
        (inscripcion,) = [
            i
            for i in await e.uow.enrollments.find_by_competition(e.competicion.id)
            if i.user_id == dentro[0]
        ]

        await WithdrawEnrollmentUseCase(e.uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), dentro[0]
        )

        assert espera in await e.plazas(e.manana)

    async def test_al_retirarse_sale_de_las_listas(self, e):
        await e.torneo()
        await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)
        (inscripcion,) = [
            i
            for i in await e.uow.enrollments.find_by_competition(e.competicion.id)
            if i.user_id == espera
        ]

        await WithdrawEnrollmentUseCase(e.uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), espera
        )

        assert await e.espera(e.manana) == []

    async def test_ampliarla_la_rellena_con_los_que_quepan(self, e):
        await e.torneo()
        await e.llena(e.manana)
        esperan = [await e.aprobado() for _ in range(4)]
        for j in esperan:
            await e.esperar(e.manana, j)
        dos_salidas = TeeSheetDTO(
            first_tee_time=time(9, 0), last_tee_time=time(9, 10), interval_minutes=10, group_size=3
        )

        await UpdateRoundUseCase(e.uow).execute(
            UpdateRoundRequestDTO(round_id=e.manana.id.value, tee_sheet=dos_salidas), e.creador
        )

        assert set(esperan[:3]) <= set(await e.plazas(e.manana))
        assert await e.espera(e.manana) == [esperan[3]]

    async def test_se_salta_al_que_ya_juega_ese_dia(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        await e.llena(e.tarde)
        primero, segundo = await e.aprobado(), await e.aprobado()
        await e.esperar(e.manana, primero)
        await e.esperar(e.manana, segundo)
        # El primero consigue plaza en la tarde (alguien la suelta): ya juega ese día
        await e.esperar(e.tarde, primero)
        tarde = await e.plazas(e.tarde)
        await e.soltar(e.tarde, tarde[0])

        await e.soltar(e.manana, dentro[0])

        assert segundo in await e.plazas(e.manana)
        assert primero not in await e.plazas(e.manana)

    async def test_asignada_sale_de_la_otra_lista_de_ese_dia(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        await e.llena(e.tarde)
        jugador = await e.aprobado()
        await e.esperar(e.manana, jugador)
        await e.esperar(e.tarde, jugador)

        await e.soltar(e.manana, dentro[0])

        assert jugador in await e.plazas(e.manana)
        assert await e.espera(e.tarde) == []

    async def test_rellenar_se_salta_a_quien_ya_juega_ese_dia_aunque_siga_en_la_lista(self, e):
        """Protección de la pieza: aunque alguien siga en la lista con plaza ese día."""
        from datetime import UTC, datetime

        from src.modules.competition.application.services.esperas_de_la_competicion import (
            EsperasDeLaCompeticion,
        )
        from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja

        await e.torneo()
        dentro = await e.llena(e.manana)
        primero, segundo = await e.aprobado(), await e.aprobado()
        await e.esperar(e.manana, primero)
        await e.esperar(e.manana, segundo)
        ahora = datetime.now(UTC)
        async with e.uow:
            # Plaza puesta a mano, sin pasar por quien lo saca de las listas
            await e.uow.plazas.add(
                PlazaEnFranja.crear(e.competicion.id, e.tarde.id, primero, ahora)
            )
            await e.uow.plazas.quitar(e.manana.id, dentro[0])
            await EsperasDeLaCompeticion(e.uow).rellenar(e.competicion, e.manana.id, ahora)

        assert segundo in await e.plazas(e.manana)
        assert primero not in await e.plazas(e.manana)


class TestAlConseguirPlaza:
    async def test_sale_de_las_listas_de_ese_dia(self, e):
        await e.torneo(jornadas=2)
        await e.llena(e.manana)
        await e.llena(e.sabado)
        jugador = await e.aprobado()
        await e.esperar(e.manana, jugador)
        await e.esperar(e.sabado, jugador)

        await e.coger(e.tarde, jugador)

        assert await e.espera(e.manana) == []
        assert await e.espera(e.sabado) == [jugador]

    async def test_al_llenar_el_cupo_sale_de_todas(self, e):
        await e.torneo(jornadas=1)
        await e.llena(e.sabado)
        jugador = await e.aprobado()
        await e.esperar(e.sabado, jugador)

        await e.coger(e.manana, jugador)

        assert await e.espera(e.sabado) == []


class TestAlCerrar:
    async def test_las_listas_se_vacian(self, e):
        from src.modules.competition.application.dto.competition_dto import (
            CloseEnrollmentsRequestDTO,
        )
        from src.modules.competition.application.use_cases.close_enrollments_use_case import (
            CloseEnrollmentsUseCase,
        )
        from tests.unit.modules.competition.application.use_cases.helpers import (
            USUARIOS_CON_GENERO,
            plaza_para_todos,
        )

        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()
        await e.esperar(e.manana, jugador)
        await plaza_para_todos(e.uow, e.competicion.id)

        await CloseEnrollmentsUseCase(e.uow, USUARIOS_CON_GENERO).execute(
            CloseEnrollmentsRequestDTO(competition_id=e.competicion.id.value), e.creador
        )

        assert await e.espera(e.manana) == []

    async def test_cerradas_ya_no_se_rellena(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)
        await e.cambiar_estado(CompetitionStatus.CLOSED)

        await CogerPlazaUseCase(e.uow).execute(
            e.tarde.id, dentro[0], e.creador, en_lugar_de=e.manana.id
        )

        assert espera not in await e.plazas(e.manana)


class TestRequiereTuAtencion:
    async def test_la_plaza_asignada_sale_hasta_entendido(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)
        await e.soltar(e.manana, dentro[0])

        antes = await MisPlazasAsignadasUseCase(e.uow).execute(espera)
        await EntendidoUseCase(e.uow).execute(e.manana.id, espera)
        despues = await MisPlazasAsignadasUseCase(e.uow).execute(espera)

        assert [(a.competition_id, a.round_id) for a in antes] == [
            (e.competicion.id.value, e.manana.id.value)
        ]
        assert antes[0].competition_name == "Medal De Octubre"
        assert despues == []

    async def test_la_que_coge_el_mismo_no_sale(self, e):
        await e.torneo()
        jugador = await e.aprobado()
        await e.coger(e.manana, jugador)

        assert await MisPlazasAsignadasUseCase(e.uow).execute(jugador) == []


class TestLoQueEncontroElRevisor:
    """La pasada del revisor sin mi contexto (8 oct 2026)."""

    async def test_salir_de_la_lista_bloquea_la_competicion(self, e):
        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()
        await e.esperar(e.manana, jugador)
        bloqueadas = []
        original = e.uow.competitions.find_by_id_for_update

        async def espia(competition_id):
            bloqueadas.append(competition_id)
            return await original(competition_id)

        e.uow.competitions.find_by_id_for_update = espia

        await DejarDeEsperarUseCase(e.uow).execute(e.manana.id, jugador, jugador)

        assert bloqueadas == [e.competicion.id]

    async def test_el_organizador_saca_a_alguien_de_la_lista(self, e):
        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()
        await e.esperar(e.manana, jugador)

        await DejarDeEsperarUseCase(e.uow).execute(e.manana.id, jugador, e.creador)

        assert await e.espera(e.manana) == []

    async def test_mover_una_franja_de_dia_limpia_las_listas_de_ese_dia(self, e):
        await e.torneo(jornadas=2)
        await e.llena(e.sabado)
        jugador = await e.aprobado()
        await e.coger(e.tarde, jugador)
        await e.esperar(e.sabado, jugador)

        # Su franja del viernes pasa al sábado: ya juega ese día
        await UpdateRoundUseCase(e.uow).execute(
            UpdateRoundRequestDTO(round_id=e.tarde.id.value, round_date=SABADO), e.creador
        )

        assert await e.espera(e.sabado) == []

    async def test_en_una_franja_ya_jugada_ni_se_espera_ni_se_rellena(self, e):
        from src.modules.competition.domain.value_objects.round_status import RoundStatus

        await e.torneo()
        dentro = await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)
        e.manana._status = RoundStatus.IN_PROGRESS
        async with e.uow:
            await e.uow.rounds.update(e.manana)

        await e.soltar(e.manana, dentro[0])
        otro = await e.aprobado()

        assert espera not in await e.plazas(e.manana)
        with pytest.raises(PlazaEnFranjaError, match="jugando"):
            await e.esperar(e.manana, otro)

    async def test_esperar_en_una_franja_que_borran_a_la_vez_es_404(self, e):
        from src.modules.competition.application.exceptions import RoundNotFoundError

        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()

        async def la_borraron(_round_id):
            return None

        e.uow.rounds.find_by_id_for_update = la_borraron

        with pytest.raises(RoundNotFoundError):
            await e.esperar(e.manana, jugador)

    async def test_requiere_tu_atencion_no_ensena_las_de_una_cancelada(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)
        await e.soltar(e.manana, dentro[0])
        await e.cambiar_estado(CompetitionStatus.CANCELLED)

        assert await MisPlazasAsignadasUseCase(e.uow).execute(espera) == []

    async def test_cancelar_vacia_las_listas(self, e):
        from src.modules.competition.application.dto.competition_dto import (
            CancelCompetitionRequestDTO,
        )
        from src.modules.competition.application.use_cases.cancel_competition_use_case import (
            CancelCompetitionUseCase,
        )

        await e.torneo()
        await e.llena(e.manana)
        await e.esperar(e.manana, await e.aprobado())

        await CancelCompetitionUseCase(e.uow).execute(
            CancelCompetitionRequestDTO(competition_id=e.competicion.id.value), e.creador
        )

        assert await e.espera(e.manana) == []

    async def test_bajar_el_cupo_de_jornadas_saca_de_las_listas_a_quien_ya_lo_llena(self, e):
        """Así nadie se queda en una lista para que luego se le salte (revisor de la 3b)."""
        from src.modules.competition.application.dto.competition_dto import (
            StrokePlaySettingsDTO,
        )
        from src.modules.competition.application.use_cases.update_stroke_play_settings_use_case import (
            UpdateStrokePlaySettingsUseCase,
        )

        await e.torneo(jornadas=2)
        await e.llena(e.sabado)
        jugador = await e.aprobado()
        await e.coger(e.manana, jugador)
        await e.esperar(e.sabado, jugador)

        await UpdateStrokePlaySettingsUseCase(e.uow).execute(
            e.competicion.id.value, StrokePlaySettingsDTO(max_matchdays_per_player=1), e.creador
        )

        assert await e.espera(e.sabado) == []

    async def test_cerrar_reabrir_y_volver_a_esperar(self, e):
        from src.modules.competition.application.dto.competition_dto import (
            CloseEnrollmentsRequestDTO,
        )
        from src.modules.competition.application.use_cases.close_enrollments_use_case import (
            CloseEnrollmentsUseCase,
        )
        from tests.unit.modules.competition.application.use_cases.helpers import (
            USUARIOS_CON_GENERO,
            plaza_para_todos,
        )

        await e.torneo()
        await e.llena(e.manana)
        jugador = await e.aprobado()
        await e.esperar(e.manana, jugador)
        await plaza_para_todos(e.uow, e.competicion.id)
        # (plaza_para_todos le da plaza en una franja de tarde: se la quitamos tras reabrir)
        await CloseEnrollmentsUseCase(e.uow, USUARIOS_CON_GENERO).execute(
            CloseEnrollmentsRequestDTO(competition_id=e.competicion.id.value), e.creador
        )
        competicion = await e.uow.competitions.find_by_id(e.competicion.id)
        competicion.reopen_enrollments()
        async with e.uow:
            await e.uow.competitions.update(competicion)
        e.competicion = competicion
        for plaza in await e.uow.plazas.de_la_competicion(e.competicion.id):
            if plaza.user_id == jugador:
                await e.soltar(await e.uow.rounds.find_by_id(plaza.round_id), jugador)

        await e.esperar(e.manana, jugador)

        assert await e.espera(e.manana) == [jugador]

    async def test_retirarse_no_suelta_la_plaza_de_una_franja_ya_jugada(self, e):
        """Tras volver atrás con sesiones jugadas: esa plaza es historial (revisor de la 3b)."""
        from src.modules.competition.domain.value_objects.round_status import RoundStatus

        await e.torneo()
        dentro = await e.llena(e.manana)
        e.manana._status = RoundStatus.COMPLETED
        async with e.uow:
            await e.uow.rounds.update(e.manana)
        (inscripcion,) = [
            i
            for i in await e.uow.enrollments.find_by_competition(e.competicion.id)
            if i.user_id == dentro[0]
        ]

        await WithdrawEnrollmentUseCase(e.uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), dentro[0]
        )

        assert dentro[0] in await e.plazas(e.manana)


class TestLoQueEncontroCodeReview:
    async def test_cancelar_bloquea_la_competicion(self, e):
        from src.modules.competition.application.dto.competition_dto import (
            CancelCompetitionRequestDTO,
        )
        from src.modules.competition.application.use_cases.cancel_competition_use_case import (
            CancelCompetitionUseCase,
        )

        await e.torneo()
        bloqueadas = []
        original = e.uow.competitions.find_by_id_for_update

        async def espia(competition_id):
            bloqueadas.append(competition_id)
            return await original(competition_id)

        e.uow.competitions.find_by_id_for_update = espia

        await CancelCompetitionUseCase(e.uow).execute(
            CancelCompetitionRequestDTO(competition_id=e.competicion.id.value), e.creador
        )

        assert bloqueadas == [e.competicion.id]

    async def test_moverle_de_una_plaza_recien_asignada_conserva_el_aviso(self, e):
        await e.torneo()
        dentro = await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)
        await e.soltar(e.manana, dentro[0])

        await CogerPlazaUseCase(e.uow).execute(
            e.tarde.id, espera, e.creador, en_lugar_de=e.manana.id
        )

        asignadas = await MisPlazasAsignadasUseCase(e.uow).execute(espera)
        assert [a.round_id for a in asignadas] == [e.tarde.id.value]

    async def test_no_avisa_de_una_plaza_en_una_franja_ya_jugada(self, e):
        from src.modules.competition.domain.value_objects.round_status import RoundStatus

        await e.torneo()
        dentro = await e.llena(e.manana)
        espera = await e.aprobado()
        await e.esperar(e.manana, espera)
        await e.soltar(e.manana, dentro[0])
        e.manana._status = RoundStatus.COMPLETED
        async with e.uow:
            await e.uow.rounds.update(e.manana)

        assert await MisPlazasAsignadasUseCase(e.uow).execute(espera) == []
