"""
La lista de espera con la inscripción directa (release social 3, tabla del 28 oct 2026).

    #    caso                                                | qué pasa
    -----|---------------------------------------------------|------------------------------
    A3   suelta su plaza / se cambia / se retira / se quita | al primero de la espera se le
         / se amplía la franja                             | avisa: `placed_from_waiting_list`
    A3   sin nadie esperando                                | ningún aviso
    W2   quien solo espera deja su última espera           | sale de la competición (WITHDRAWN)
    W2   ... también si le saca el organizador              | igual
    W2   le queda otra espera, o tiene plaza                | sigue inscrito
    A4   al cerrar, quien sigue solo en espera              | sale, con `no_place` y `left`
    A4   quien no tiene franja ni espera                    | sigue bloqueando el cierre
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import CloseEnrollmentsRequestDTO
from src.modules.competition.application.dto.enrollment_dto import (
    RemoveEnrolledPlayerRequestDTO,
    WithdrawEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.round_match_dto import (
    DeleteRoundRequestDTO,
    TeeSheetDTO,
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.services.franjas_al_cerrar import (
    PlayersWithoutTeeWindowError,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.delete_round_use_case import (
    DeleteRoundUseCase,
)
from src.modules.competition.application.use_cases.listas_de_espera_use_case import (
    DejarDeEsperarUseCase,
)
from src.modules.competition.application.use_cases.plazas_en_franjas_use_case import (
    CogerPlazaUseCase,
    SoltarPlazaUseCase,
)
from src.modules.competition.application.use_cases.remove_enrolled_player_use_case import (
    RemoveEnrolledPlayerUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio

DIA = date.today() + timedelta(days=30)


class _Actividad:
    def __init__(self):
        self.llamadas = []

    def __getattr__(self, nombre):
        async def apunta(*args, **kwargs):
            self.llamadas.append((nombre, args))

        return apunta

    def de(self, nombre):
        return [args for n, args in self.llamadas if n == nombre]


class _E:
    async def montar(self):
        self.uow = InMemoryUnitOfWork()
        self.creador = UserId(uuid4())
        self.actividad = _Actividad()
        self.competicion = Competition(
            id=CompetitionId(uuid4()),
            creator_id=self.creador,
            name=CompetitionName("Medal de noviembre"),
            dates=DateRange(DIA, DIA),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            tournament_type=TournamentType.MEDAL,
            status=CompetitionStatus.ACTIVE,
            category_limits=[Decimal("12.0")],
            visibility=Visibility.PUBLIC,
            max_players=40,
        )
        self.nueve = self._franja(time(9, 0), SessionType.MORNING)
        self.diez = self._franja(time(10, 0), SessionType.AFTERNOON)
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
            await self.uow.rounds.add(self.nueve)
            await self.uow.rounds.add(self.diez)
        return self

    def _franja(self, hora, sesion):
        return Round.create_franja(
            competition_id=self.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=DIA,
            session_type=sesion,
            hoja_de_salidas=HojaDeSalidas(hora, hora, 10, 3),
        )

    async def inscrito(self, franja=None, espera=None, entro_esperando=False) -> UserId:
        quien = UserId(uuid4())
        inscripcion = Enrollment.direct_enroll(
            id=EnrollmentId.generate(), competition_id=self.competicion.id, user_id=quien
        )
        if entro_esperando:
            inscripcion.entra_esperando()
        async with self.uow:
            await self.uow.enrollments.add(inscripcion)
            ahora = datetime.now(UTC)
            if franja is not None:
                await self.uow.plazas.add(
                    PlazaEnFranja.crear(self.competicion.id, franja.id, quien, ahora)
                )
            for f in espera or []:
                await self.uow.esperas.add(
                    EsperaEnFranja.crear(self.competicion.id, f.id, quien, ahora)
                )
        return quien

    async def llena_con_uno_esperando(self, franja):
        dentro = [await self.inscrito(franja) for _ in range(3)]
        espera = await self.inscrito(espera=[franja], entro_esperando=True)
        return dentro, espera

    async def inscripcion(self, quien):
        async with self.uow:
            return await self.uow.enrollments.find_by_user_and_competition(
                quien, self.competicion.id
            )

    async def plazas_de(self, quien):
        async with self.uow:
            return [
                p.round_id
                for p in await self.uow.plazas.de_la_competicion(self.competicion.id)
                if p.user_id == quien
            ]

    def avisados(self):
        return [
            (franja.id, quien) for _, franja, quien in self.actividad.de("placed_from_waiting_list")
        ]


@pytest.fixture
async def e():
    return await _E().montar()


class TestA3AvisoDePlaza:
    async def test_al_soltar_una_plaza_se_avisa_al_primero(self, e):
        dentro, espera = await e.llena_con_uno_esperando(e.nueve)

        await SoltarPlazaUseCase(e.uow, actividad=e.actividad).execute(
            e.nueve.id, dentro[0], dentro[0]
        )

        assert await e.plazas_de(espera) == [e.nueve.id]
        assert e.avisados() == [(e.nueve.id, espera)]

    async def test_al_cambiarse_de_franja_se_avisa_al_de_la_que_deja(self, e):
        dentro, espera = await e.llena_con_uno_esperando(e.nueve)

        await CogerPlazaUseCase(e.uow, actividad=e.actividad).execute(
            e.diez.id, dentro[0], dentro[0], en_lugar_de=e.nueve.id
        )

        assert e.avisados() == [(e.nueve.id, espera)]

    async def test_al_retirarse_se_avisa(self, e):
        dentro, espera = await e.llena_con_uno_esperando(e.nueve)
        inscripcion = await e.inscripcion(dentro[0])

        await WithdrawEnrollmentUseCase(e.uow, actividad=e.actividad).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value),
            dentro[0],
        )

        assert e.avisados() == [(e.nueve.id, espera)]

    async def test_al_quitarle_el_organizador_se_avisa(self, e):
        dentro, espera = await e.llena_con_uno_esperando(e.nueve)
        inscripcion = await e.inscripcion(dentro[0])

        await RemoveEnrolledPlayerUseCase(e.uow, actividad=e.actividad).execute(
            RemoveEnrolledPlayerRequestDTO(enrollment_id=inscripcion.id.value), e.creador
        )

        assert e.avisados() == [(e.nueve.id, espera)]

    async def test_al_ampliar_la_franja_se_avisa(self, e):
        _, espera = await e.llena_con_uno_esperando(e.nueve)

        await UpdateRoundUseCase(e.uow, actividad=e.actividad).execute(
            UpdateRoundRequestDTO(
                round_id=e.nueve.id.value,
                tee_sheet=TeeSheetDTO(
                    first_tee_time=time(9, 0),
                    last_tee_time=time(9, 10),
                    interval_minutes=10,
                    group_size=3,
                ),
            ),
            e.creador,
        )

        assert e.avisados() == [(e.nueve.id, espera)]

    async def test_sin_nadie_esperando_no_hay_aviso(self, e):
        quien = await e.inscrito(e.nueve)

        await SoltarPlazaUseCase(e.uow, actividad=e.actividad).execute(e.nueve.id, quien, quien)

        assert e.avisados() == []


class TestW2DejarLaUltimaEspera:
    async def test_quien_solo_espera_y_la_deja_sale_de_la_competicion(self, e):
        _, espera = await e.llena_con_uno_esperando(e.nueve)

        await DejarDeEsperarUseCase(e.uow, actividad=e.actividad).execute(
            e.nueve.id, espera, espera
        )

        assert (await e.inscripcion(espera)).status == EnrollmentStatus.WITHDRAWN
        assert [args[1] for args in e.actividad.de("left")] == [espera]

    async def test_tambien_si_le_saca_el_organizador(self, e):
        _, espera = await e.llena_con_uno_esperando(e.nueve)

        await DejarDeEsperarUseCase(e.uow, actividad=e.actividad).execute(
            e.nueve.id, espera, e.creador
        )

        assert (await e.inscripcion(espera)).status == EnrollmentStatus.WITHDRAWN

    async def test_si_le_queda_otra_espera_sigue_inscrito(self, e):
        for _ in range(3):
            await e.inscrito(e.nueve)
        for _ in range(3):
            await e.inscrito(e.diez)
        quien = await e.inscrito(espera=[e.nueve, e.diez], entro_esperando=True)

        await DejarDeEsperarUseCase(e.uow, actividad=e.actividad).execute(e.nueve.id, quien, quien)

        assert (await e.inscripcion(quien)).status == EnrollmentStatus.APPROVED
        assert e.actividad.de("left") == []

    async def test_quien_entro_sin_esperar_y_deja_la_espera_sigue_inscrito(self, e):
        """Entró por invitación o a mano, sin franja: el organizador lo coloca (28 oct)."""
        for _ in range(3):
            await e.inscrito(e.nueve)
        quien = await e.inscrito(espera=[e.nueve])

        await DejarDeEsperarUseCase(e.uow, actividad=e.actividad).execute(e.nueve.id, quien, quien)

        assert (await e.inscripcion(quien)).status == EnrollmentStatus.APPROVED
        assert e.actividad.de("left") == []

    async def test_quien_entro_esperando_y_ya_tiene_plaza_sigue_inscrito(self, e):
        for _ in range(3):
            await e.inscrito(e.nueve)
        quien = await e.inscrito(e.diez, espera=[e.nueve], entro_esperando=True)

        await DejarDeEsperarUseCase(e.uow, actividad=e.actividad).execute(e.nueve.id, quien, quien)

        assert (await e.inscripcion(quien)).status == EnrollmentStatus.APPROVED

    async def test_con_plaza_sigue_inscrito(self, e):
        for _ in range(3):
            await e.inscrito(e.nueve)
        quien = await e.inscrito(e.diez, espera=[e.nueve])

        await DejarDeEsperarUseCase(e.uow, actividad=e.actividad).execute(e.nueve.id, quien, quien)

        assert (await e.inscripcion(quien)).status == EnrollmentStatus.APPROVED


class TestA4AlCerrar:
    async def _cerrar(self, e):
        await CloseEnrollmentsUseCase(e.uow, USUARIOS_CON_GENERO, actividad=e.actividad).execute(
            CloseEnrollmentsRequestDTO(competition_id=e.competicion.id.value), e.creador
        )

    async def test_quien_sigue_solo_en_espera_sale_con_su_aviso(self, e):
        _, espera = await e.llena_con_uno_esperando(e.nueve)

        await self._cerrar(e)

        assert (await e.inscripcion(espera)).status == EnrollmentStatus.WITHDRAWN
        [(competicion, inscripciones)] = e.actividad.de("no_place")
        assert competicion.id == e.competicion.id
        assert [i.user_id for i in inscripciones] == [espera]
        assert [args[1] for args in e.actividad.de("left")] == [espera]
        async with e.uow:
            cerrada = await e.uow.competitions.find_by_id(e.competicion.id)
        assert cerrada.status == CompetitionStatus.CLOSED

    async def test_quien_tiene_plaza_y_espera_otro_dia_sigue(self, e):
        for _ in range(3):
            await e.inscrito(e.nueve)
        quien = await e.inscrito(e.diez, espera=[e.nueve])

        await self._cerrar(e)

        assert (await e.inscripcion(quien)).status == EnrollmentStatus.APPROVED
        assert e.actividad.de("no_place") == []

    async def test_quien_entro_sin_esperar_y_espera_bloquea_el_cierre(self, e):
        for _ in range(3):
            await e.inscrito(e.nueve)
        await e.inscrito(espera=[e.nueve])

        with pytest.raises(PlayersWithoutTeeWindowError):
            await self._cerrar(e)

    async def test_quien_entro_esperando_sale_aunque_ya_no_espere(self, e):
        await e.inscrito(entro_esperando=True)

        await self._cerrar(e)

        assert len(e.actividad.de("no_place")) == 1

    async def test_sin_franja_ni_espera_sigue_bloqueando(self, e):
        await e.inscrito()

        with pytest.raises(PlayersWithoutTeeWindowError):
            await self._cerrar(e)

        assert e.actividad.de("no_place") == []


class TestBorrarUnaFranja:
    async def _borrar(self, e, franja):
        await DeleteRoundUseCase(e.uow, actividad=e.actividad).execute(
            DeleteRoundRequestDTO(round_id=franja.id.value), e.creador
        )

    async def test_quien_solo_esperaba_en_ella_sale_con_su_aviso(self, e):
        _, espera = await e.llena_con_uno_esperando(e.nueve)
        await self._borrar_llena(e, e.nueve)

        assert (await e.inscripcion(espera)).status == EnrollmentStatus.WITHDRAWN
        [(competicion, franja, inscripcion)] = e.actividad.de("window_removed")
        assert competicion.id == e.competicion.id
        assert franja.id == e.nueve.id
        assert inscripcion.user_id == espera
        assert [args[1] for args in e.actividad.de("left")] == [espera]

    async def _borrar_llena(self, e, franja):
        """Con plazas no se borra: se sueltan antes las de los de dentro."""
        async with e.uow:
            for plaza in list(await e.uow.plazas.de_la_competicion(e.competicion.id)):
                if plaza.round_id == franja.id:
                    await e.uow.plazas.quitar(franja.id, plaza.user_id)
        await self._borrar(e, franja)

    async def test_si_le_queda_otra_espera_sigue(self, e):
        for _ in range(3):
            await e.inscrito(e.nueve)
        for _ in range(3):
            await e.inscrito(e.diez)
        quien = await e.inscrito(espera=[e.nueve, e.diez], entro_esperando=True)

        await self._borrar_llena(e, e.nueve)

        assert (await e.inscripcion(quien)).status == EnrollmentStatus.APPROVED
        assert e.actividad.de("window_removed") == []

    async def test_quien_entro_sin_esperar_sigue(self, e):
        for _ in range(3):
            await e.inscrito(e.nueve)
        quien = await e.inscrito(espera=[e.nueve])

        await self._borrar_llena(e, e.nueve)

        assert (await e.inscripcion(quien)).status == EnrollmentStatus.APPROVED


class TestPrimeraPlaza:
    async def test_quien_entro_esperando_y_coge_plaza_a_mano_ya_cuenta_como_inscrito(self, e):
        for _ in range(3):
            await e.inscrito(e.nueve)
        quien = await e.inscrito(espera=[e.nueve], entro_esperando=True)

        await CogerPlazaUseCase(e.uow, actividad=e.actividad).execute(e.diez.id, quien, quien)

        [(_, inscripcion, aceptada)] = e.actividad.de("enrolled")
        assert inscripcion.user_id == quien
        assert aceptada is False

    async def test_quien_ya_tenia_plaza_y_se_cambia_no_repite_el_aviso(self, e):
        quien = await e.inscrito(e.nueve)

        await CogerPlazaUseCase(e.uow, actividad=e.actividad).execute(
            e.diez.id, quien, quien, en_lugar_de=e.nueve.id
        )

        assert e.actividad.de("enrolled") == []
