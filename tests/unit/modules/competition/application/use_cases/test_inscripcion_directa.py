"""
Inscripción directa en las públicas (release social 3, tabla aprobada el 28 oct 2026).

En una pública ya no se pide plaza: se entra. En un stroke play con franjas se
elige franja con hueco, o la espera de una llena, en el mismo paso.

    #    caso                                             | qué pasa
    -----|------------------------------------------------|---------------------------------
    D1   Ryder (o sin franjas) con plaza                  | APPROVED directo, con su barra
    D2   Ryder llena                                      | CompetitionFullError
    D3   franja con hueco                                 | APPROVED y con su plaza, de golpe
    D4   con franjas y sin elegir                         | TeeWindowRequiredError
    D5   franja llena sin pedir la espera                 | TeeWindowFullError
    D6   franja llena pidiendo la espera                  | APPROVED y en su espera
    D7   espera de una franja con hueco                   | TeeWindowHasRoomError
    D8   con franjas el máximo de jugadores no se mira    | entra aunque `max_players` esté lleno
    D9   privada                                          | CompetitionIsPrivateError
    D10  borrador que ya debía abrirse                    | se abre y entra
    D11  borrador antes de su hora, o cerrada             | CompetitionNotActiveError
    D13  con una inscripción vieja                        | se reutiliza, APPROVED
    D14  con una invitación pendiente                     | la invitación queda aceptada
    D16  una franja de otra competición                   | TeeWindowNotFoundError
    A1   el organizador recibe «X se ha apuntado»         | `joined`, con su franja o su espera
    A2   «se ha apuntado» de amigos solo con plaza        | `enrolled` solo si no espera
"""

from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    AlreadyEnrolledError,
    CompetitionFullError,
    CompetitionIsPrivateError,
    CompetitionNotActiveError,
    RequestEnrollmentUseCase,
    TeeWindowFullError,
    TeeWindowHasRoomError,
    TeeWindowNotFoundError,
    TeeWindowRequiredError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.exceptions.competition_violations import (
    InvitationExpiredViolation,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
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
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

DENTRO_DE_UN_MES = date.today() + timedelta(days=30)


class _Usuarios:
    """Todos con género, hándicap y su correo."""

    async def find_by_id(self, user_id):
        return SimpleNamespace(
            id=user_id,
            gender=Gender.MALE,
            handicap=Decimal("12.0"),
            email=SimpleNamespace(value=f"{user_id.value}@example.com"),
        )


class _Zona:
    async def for_competition(self, competition):
        return "Europe/Madrid"


class _Actividad:
    """Lo que se le cuenta a Actividad, en orden."""

    def __init__(self):
        self.llamadas = []

    def __getattr__(self, nombre):
        async def apunta(*args):
            self.llamadas.append((nombre, args))

        return apunta

    def de(self, nombre):
        return [args for n, args in self.llamadas if n == nombre]


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.creador = UserId(uuid4())
        self.actividad = _Actividad()

    async def ryder(self, max_players=4, visibility=Visibility.PUBLIC, **extra) -> Competition:
        datos = {
            "status": CompetitionStatus.ACTIVE,
            "dates": DateRange(DENTRO_DE_UN_MES, DENTRO_DE_UN_MES + timedelta(days=1)),
        }
        datos.update(extra)
        self.competicion = Competition(
            id=CompetitionId.generate(),
            creator_id=self.creador,
            name=CompetitionName("Ryder del club"),
            location=Location(CountryCode("ES")),
            team_1_name="Europa",
            team_2_name="América",
            play_mode=PlayMode.SCRATCH,
            max_players=max_players,
            visibility=visibility,
            **datos,
        )
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
        return self.competicion

    async def medal(self, con_franjas=True, max_players=40) -> Competition:
        self.competicion = Competition(
            id=CompetitionId.generate(),
            creator_id=self.creador,
            name=CompetitionName("Medal de noviembre"),
            dates=DateRange(DENTRO_DE_UN_MES, DENTRO_DE_UN_MES),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            tournament_type=TournamentType.MEDAL,
            status=CompetitionStatus.ACTIVE,
            category_limits=[Decimal("12.0")],
            max_players=max_players,
            visibility=Visibility.PUBLIC,
        )
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
        if con_franjas:
            # De una sola salida de 3: cupo 3
            self.nueve = await self.franja(time(9, 0))
            self.diez = await self.franja(time(10, 0), SessionType.AFTERNOON)
        return self.competicion

    async def franja(self, hora, sesion=SessionType.MORNING, competicion=None) -> Round:
        franja = Round.create_franja(
            competition_id=(competicion or self.competicion).id,
            golf_course_id=GolfCourseId.generate(),
            round_date=DENTRO_DE_UN_MES,
            session_type=sesion,
            hoja_de_salidas=HojaDeSalidas(hora, hora, 10, 3),
        )
        async with self.uow:
            await self.uow.rounds.add(franja)
        return franja

    async def dentro(self, franja=None) -> UserId:
        quien = UserId(uuid4())
        async with self.uow:
            await self.uow.enrollments.add(
                Enrollment.direct_enroll(
                    id=EnrollmentId.generate(),
                    competition_id=self.competicion.id,
                    user_id=quien,
                )
            )
            if franja is not None:
                await self.uow.plazas.add(
                    PlazaEnFranja.crear(self.competicion.id, franja.id, quien, _ahora())
                )
        return quien

    async def llena(self, franja):
        for _ in range(3):
            await self.dentro(franja)

    async def entra(self, quien=None, franja=None, espera=False, tee_color=None):
        quien = quien or UserId(uuid4())
        caso = RequestEnrollmentUseCase(
            self.uow, _Usuarios(), zonas=_Zona(), actividad=self.actividad
        )
        respuesta = await caso.execute(
            RequestEnrollmentRequestDTO(
                competition_id=self.competicion.id.value,
                user_id=quien.value,
                tee_color=tee_color,
                round_id=franja.id.value if franja else None,
                waiting_list=espera,
            )
        )
        return quien, respuesta

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

    async def esperas_de(self, quien):
        async with self.uow:
            return [
                e.round_id
                for e in await self.uow.esperas.de_la_competicion(self.competicion.id)
                if e.user_id == quien
            ]


def _ahora():
    from datetime import UTC, datetime

    return datetime.now(UTC)


@pytest.fixture
def e():
    return _Escenario()


class TestSinFranjas:
    async def test_d1_en_una_ryder_con_plaza_entra_directo_con_su_barra(self, e):
        await e.ryder()

        quien, respuesta = await e.entra(tee_color="WHITE")

        assert respuesta.status == "APPROVED"
        inscripcion = await e.inscripcion(quien)
        assert inscripcion.status == EnrollmentStatus.APPROVED
        assert inscripcion.tee_color.value == "WHITE"

    async def test_d1_un_stroke_play_sin_franjas_montadas_entra_solo_con_la_barra(self, e):
        await e.medal(con_franjas=False)

        quien, respuesta = await e.entra()

        assert respuesta.status == "APPROVED"
        assert await e.plazas_de(quien) == []

    async def test_d2_en_una_ryder_llena_no_entra(self, e):
        await e.ryder(max_players=2)
        await e.dentro()
        await e.dentro()

        with pytest.raises(CompetitionFullError):
            await e.entra()

    async def test_d9_en_una_privada_no_se_entra(self, e):
        await e.ryder(visibility=Visibility.PRIVATE)

        with pytest.raises(CompetitionIsPrivateError):
            await e.entra()

    async def test_d10_un_borrador_al_que_ya_le_toca_abrir_se_abre_y_entra(self, e):
        await e.ryder(
            status=CompetitionStatus.DRAFT,
            dates=DateRange(date.today() + timedelta(days=5), date.today() + timedelta(days=6)),
            enrollment_opens_days_before=10,
        )

        _, respuesta = await e.entra()

        assert respuesta.status == "APPROVED"
        async with e.uow:
            competicion = await e.uow.competitions.find_by_id(e.competicion.id)
        assert competicion.status == CompetitionStatus.ACTIVE

    async def test_d11_un_borrador_antes_de_su_hora_no_admite(self, e):
        await e.ryder(
            status=CompetitionStatus.DRAFT,
            dates=DateRange(date.today() + timedelta(days=30), date.today() + timedelta(days=31)),
            enrollment_opens_days_before=10,
        )

        with pytest.raises(CompetitionNotActiveError):
            await e.entra()

    async def test_d11_con_las_inscripciones_cerradas_no_se_entra(self, e):
        await e.ryder(status=CompetitionStatus.CLOSED)

        with pytest.raises(CompetitionNotActiveError):
            await e.entra()

    async def test_d13_con_una_inscripcion_vieja_se_reutiliza(self, e):
        await e.ryder()
        quien = await e.dentro()
        async with e.uow:
            vieja = await e.uow.enrollments.find_by_user_and_competition(quien, e.competicion.id)
            vieja.withdraw()
            await e.uow.enrollments.update(vieja)

        _, respuesta = await e.entra(quien)

        assert respuesta.id == vieja.id.value
        assert (await e.inscripcion(quien)).status == EnrollmentStatus.APPROVED

    async def test_d14_con_una_invitacion_pendiente_queda_aceptada(self, e):
        await e.ryder()
        quien = UserId(uuid4())
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=e.competicion.id,
            inviter_id=e.creador,
            invitee_email=f"{quien.value}@example.com",
            invitee_user_id=quien,
        )
        async with e.uow:
            await e.uow.invitations.add(invitacion)

        await e.entra(quien)

        async with e.uow:
            despues = await e.uow.invitations.find_by_id(invitacion.id)
        assert despues.status == InvitationStatus.ACCEPTED
        assert [args[0].id for args in e.actividad.de("invitation_answered")] == [invitacion.id]

    async def test_d14_tambien_la_que_se_mando_a_su_correo_sin_cuenta(self, e):
        await e.ryder()
        quien = UserId(uuid4())
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=e.competicion.id,
            inviter_id=e.creador,
            invitee_email=f"{quien.value}@example.com",
        )
        async with e.uow:
            await e.uow.invitations.add(invitacion)

        await e.entra(quien)

        async with e.uow:
            despues = await e.uow.invitations.find_by_id(invitacion.id)
        assert despues.status == InvitationStatus.ACCEPTED

    async def test_d14_la_de_otra_competicion_no_se_toca(self, e):
        otra = await e.ryder()
        quien = UserId(uuid4())
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=otra.id,
            inviter_id=e.creador,
            invitee_email=f"{quien.value}@example.com",
            invitee_user_id=quien,
        )
        async with e.uow:
            await e.uow.invitations.add(invitacion)
        await e.ryder()

        await e.entra(quien)

        async with e.uow:
            despues = await e.uow.invitations.find_by_id(invitacion.id)
        assert despues.status == InvitationStatus.PENDING

    async def test_d1_con_franja_en_una_ryder_no_vale(self, e):
        otra = await e.medal()
        franja = e.nueve
        await e.ryder()
        assert otra.id != e.competicion.id

        with pytest.raises(TeeWindowNotFoundError):
            await e.entra(franja=franja)


class TestConFranjas:
    async def test_d3_con_hueco_entra_y_coge_su_plaza(self, e):
        await e.medal()

        quien, respuesta = await e.entra(franja=e.nueve)

        assert respuesta.status == "APPROVED"
        assert respuesta.round_id == e.nueve.id.value
        assert respuesta.waiting is False
        assert await e.plazas_de(quien) == [e.nueve.id]
        assert await e.esperas_de(quien) == []

    async def test_d4_sin_elegir_franja_no_entra(self, e):
        await e.medal()

        with pytest.raises(TeeWindowRequiredError):
            await e.entra()

        assert len(e.uow.enrollments._enrollments) == 0

    async def test_ya_inscrito_es_un_409_aunque_no_elija_franja(self, e):
        await e.medal()
        quien = await e.dentro(e.nueve)

        with pytest.raises(AlreadyEnrolledError):
            await e.entra(quien)

    async def test_d6_quien_entra_esperando_queda_marcado(self, e):
        await e.medal()
        await e.llena(e.nueve)

        quien, _ = await e.entra(franja=e.nueve, espera=True)

        assert (await e.inscripcion(quien)).entered_waiting is True

    async def test_d3_quien_entra_con_plaza_no(self, e):
        await e.medal()

        quien, _ = await e.entra(franja=e.nueve)

        assert (await e.inscripcion(quien)).entered_waiting is False

    async def test_d5_franja_llena_sin_pedir_la_espera(self, e):
        await e.medal()
        await e.llena(e.nueve)

        with pytest.raises(TeeWindowFullError):
            await e.entra(franja=e.nueve)

    async def test_d6_franja_llena_pidiendo_la_espera_entra_y_espera(self, e):
        await e.medal()
        await e.llena(e.nueve)

        quien, respuesta = await e.entra(franja=e.nueve, espera=True)

        assert respuesta.status == "APPROVED"
        assert respuesta.waiting is True
        assert await e.plazas_de(quien) == []
        assert await e.esperas_de(quien) == [e.nueve.id]

    async def test_d7_la_espera_de_una_franja_con_hueco_no(self, e):
        await e.medal()

        with pytest.raises(TeeWindowHasRoomError):
            await e.entra(franja=e.nueve, espera=True)

    async def test_d8_con_franjas_el_maximo_de_jugadores_no_se_mira(self, e):
        await e.medal(max_players=2)
        await e.dentro(e.diez)
        await e.dentro(e.diez)
        await e.dentro(e.diez)

        _, respuesta = await e.entra(franja=e.nueve)

        assert respuesta.status == "APPROVED"

    async def test_d16_una_franja_de_otra_competicion_no_vale(self, e):
        await e.medal()
        mia = e.competicion
        ajena = await e.medal()
        e.competicion = mia
        franja_ajena = await e.franja(time(11, 0), competicion=ajena)

        with pytest.raises(TeeWindowNotFoundError):
            await e.entra(franja=franja_ajena)

    async def test_d3_nada_se_escribe_si_la_franja_no_vale(self, e):
        await e.medal()
        await e.llena(e.nueve)
        antes = len(e.uow.enrollments._enrollments)

        with pytest.raises(TeeWindowFullError):
            await e.entra(franja=e.nueve)

        assert len(e.uow.enrollments._enrollments) == antes


class TestAvisos:
    async def test_a1_al_organizador_le_llega_que_se_ha_apuntado_con_su_franja(self, e):
        await e.medal()

        quien, _ = await e.entra(franja=e.nueve)

        [(competicion, inscripcion, franja, espera)] = e.actividad.de("joined")
        assert competicion.id == e.competicion.id
        assert inscripcion.user_id == quien
        assert franja.id == e.nueve.id
        assert espera is False

    async def test_a1_y_que_se_ha_apuntado_a_la_espera(self, e):
        await e.medal()
        await e.llena(e.nueve)

        await e.entra(franja=e.nueve, espera=True)

        [(_, _, franja, espera)] = e.actividad.de("joined")
        assert franja.id == e.nueve.id
        assert espera is True

    async def test_a1_sin_franjas_va_sin_franja(self, e):
        await e.ryder()

        await e.entra()

        [(_, _, franja, espera)] = e.actividad.de("joined")
        assert franja is None
        assert espera is False

    async def test_a1_el_organizador_que_se_apunta_a_si_mismo_no_se_avisa(self, e):
        await e.ryder()

        await e.entra(e.creador)

        assert e.actividad.de("joined") == []

    async def test_a2_con_plaza_sale_su_aviso_de_inscrito(self, e):
        await e.medal()

        quien, _ = await e.entra(franja=e.nueve)

        [(_, inscripcion, aceptada)] = e.actividad.de("enrolled")
        assert inscripcion.user_id == quien
        assert aceptada is False

    async def test_a2_solo_en_espera_no_sale_el_de_inscrito(self, e):
        await e.medal()
        await e.llena(e.nueve)

        await e.entra(franja=e.nueve, espera=True)

        assert e.actividad.de("enrolled") == []

    async def test_a_si_no_entra_no_se_avisa_de_nada(self, e):
        await e.medal()
        await e.llena(e.nueve)

        with pytest.raises(TeeWindowFullError):
            await e.entra(franja=e.nueve)

        assert e.actividad.llamadas == []


class TestTrasElCodeReview:
    """Hallazgos del /code-review de la BE PR A (28 oct 2026)."""

    async def test_una_solicitud_pendiente_de_antes_entra_al_apuntarse(self, e):
        await e.ryder()
        quien = UserId(uuid4())
        async with e.uow:
            vieja = Enrollment.request(
                id=EnrollmentId.generate(), competition_id=e.competicion.id, user_id=quien
            )
            await e.uow.enrollments.add(vieja)

        _, respuesta = await e.entra(quien)

        assert respuesta.id == vieja.id.value
        assert respuesta.status == "APPROVED"

    async def test_si_la_invitacion_no_se_puede_aceptar_entra_igual(self, e, monkeypatch):
        await e.ryder()
        quien = UserId(uuid4())
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=e.competicion.id,
            inviter_id=e.creador,
            invitee_email=f"{quien.value}@example.com",
            invitee_user_id=quien,
        )
        async with e.uow:
            await e.uow.invitations.add(invitacion)

        def caducada(self):
            raise InvitationExpiredViolation("caducó justo ahora")

        monkeypatch.setattr(Invitation, "accept", caducada)

        _, respuesta = await e.entra(quien)

        assert respuesta.status == "APPROVED"
        assert e.actividad.de("invitation_answered") == []

    async def test_pedir_la_espera_sin_franja_es_un_error(self, e):
        await e.ryder()

        with pytest.raises(TeeWindowRequiredError):
            await e.entra(espera=True)
