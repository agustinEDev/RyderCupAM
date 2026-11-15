"""
Las invitaciones con la inscripción cerrada, y B-02 rehecho (Agustín, 15 nov 2026).

En código, «en lista de espera» de una invitación es `ON_HOLD`: no tiene nada que
ver con la lista de espera de las franjas de un stroke play (`esperas`).

| Caso | Situación                                                   | Qué pasa                                       |
|------|-------------------------------------------------------------|------------------------------------------------|
| P1   | se cierra (a mano, por el plazo o al nombrar capitanes)     | las PENDING pasan a ON_HOLD; su aviso de       |
|      | con invitaciones pendientes                                 | invitado se retira; las caducadas, EXPIRED     |
| P1   | el invitado acepta una ON_HOLD                              | INVITATION_ON_HOLD, sigue ON_HOLD, no entra    |
| P1   | el invitado rechaza una ON_HOLD / el organizador la retira  | DECLINED / CANCELLED                           |
| P1   | una PENDING que se coló en una cerrada y se acepta          | pasa a ON_HOLD e INVITATION_ON_HOLD            |
| P1   | el invitado de una privada con la suya ON_HOLD              | sigue viéndola; la ficha no le ofrece aceptar  |
| P2   | el organizador reabre                                       | ON_HOLD → PENDING, aviso «ya puedes aceptar»   |
|      |                                                             | a cada invitado con cuenta; se acepta          |
| P2   | caducó mientras esperaba                                    | EXPIRED, sin aviso                             |
| P2   | se reabre sola al mover el torneo (R3)                      | igual que al reabrir                           |
| P3   | empieza (a mano o por el primer golpe) o se cancela         | ON_HOLD → NO_ROOM, aviso «no hubo plaza»       |
| B1   | el organizador inscribe a mano                              | ya no existe: ni ruta, ni caso de uso          |
| B2   | aprobar una inscripción que el jugador cerró                | no: solo se aprueba lo que él pidió            |
| B3   | equipos formados, sin partidos: el organizador invita       | puede (por id y por correo)                    |
| B3   | ... el invitado acepta                                      | entra, equipos deshechos, aviso al organizador |
| B3   | con partidos: invitar o aceptar                             | TEAMS_FORMED                                   |
| B3   | con la sala de draft abierta: invitar o aceptar             | DRAFT_IN_PROGRESS                              |
| B4   | reabierta, entra uno y se vuelve a cerrar                   | otra actualización de la RFEG, para todos      |
"""

import importlib.util
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CancelCompetitionRequestDTO,
    CloseEnrollmentsRequestDTO,
    NameCaptainsRequestDTO,
    ReopenEnrollmentsRequestDTO,
    StartCompetitionRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import HandleEnrollmentRequestDTO
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.baja_de_la_competicion import (
    DraftInProgressError,
)
from src.modules.competition.application.services.equipos_formados import TeamsFormedError
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    en_espera_las_pendientes,
    sin_plaza_para_las_que_esperan,
    vuelven_las_que_esperan,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
)
from src.modules.competition.application.use_cases.cancel_invitation_use_case import (
    CancelInvitationUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.entities.enrollment import Enrollment, EnrollmentStateError
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
    InvitationOnHoldViolation,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.draft_id import DraftId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UsuariosEnMemoria,
)
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases import (
    test_plazo_respuestas_del_15_nov as r3,
)
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    create_approved_enrollment,
    create_competition,
)
from tests.unit.modules.competition.application.use_cases.test_deshacer_equipos import _montar
from tests.unit.modules.competition.application.use_cases.test_equipos_formados_congelados import (
    _con_partidos,
    _reabierta,
)

pytestmark = pytest.mark.asyncio


class _Actividad:
    """Apunta cada aviso que se da; lo que no se mire, no hace nada."""

    def __init__(self):
        self.avisos: list[tuple] = []

    def __getattr__(self, nombre):
        async def apunta(*args, **_kwargs):
            self.avisos.append((nombre, *args))

        return apunta

    def de(self, nombre) -> list[tuple]:
        return [a[1:] for a in self.avisos if a[0] == nombre]


async def _usuarios():
    """Un invitado con cuenta, con género (aceptar lo exige)."""
    usuarios = UsuariosEnMemoria()
    invitado = User.create(
        first_name="Eva",
        last_name="Gil",
        email_str=f"eva_{uuid4().hex[:6]}@example.com",
        plain_password="SecureP@ssw0rd123",
        gender=Gender.FEMALE,
    )
    async with usuarios:
        await usuarios.users.save(invitado)
        await usuarios.commit()
    return usuarios, invitado


async def _invita(uow, comp_id: CompetitionId, invitado: User, **mas) -> Invitation:
    async with uow:
        organizador = (await uow.competitions.find_by_id(comp_id)).creator_id
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=comp_id,
            inviter_id=organizador,
            invitee_email=str(invitado.email),
            invitee_user_id=invitado.id,
        )
        for campo, valor in mas.items():
            setattr(invitacion, campo, valor)
        await uow.invitations.add(invitacion)
        await uow.commit()
    return invitacion


async def _abierta_con_invitado():
    """Una Ryder abierta, con dos inscritos y una invitación pendiente."""
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    creada = await create_competition(uow, organizador)
    comp_id = CompetitionId(creada.id)
    otro = UserId(uuid4())
    await create_approved_enrollment(uow, creada.id, otro)
    usuarios, invitado = await _usuarios()
    invitacion = await _invita(uow, comp_id, invitado)
    return uow, comp_id, organizador, otro, usuarios, invitado, invitacion


async def _estado(uow, invitacion: Invitation) -> InvitationStatus:
    async with uow:
        return (await uow.invitations.find_by_id(invitacion.id)).status


async def _cierra(uow, comp_id, organizador, actividad=None, lanzador=None):
    return await CloseEnrollmentsUseCase(uow, lanzador=lanzador, actividad=actividad).execute(
        CloseEnrollmentsRequestDTO(competition_id=comp_id.value), organizador
    )


async def _reabre(uow, comp_id, organizador, actividad=None):
    return await ReopenEnrollmentsUseCase(uow, actividad=actividad).execute(
        ReopenEnrollmentsRequestDTO(competition_id=comp_id.value), organizador
    )


def _responde(usuarios, uow, invitacion, invitado, accion, actividad=None):
    return RespondToInvitationUseCase(uow, usuarios, actividad=actividad).execute(
        RespondInvitationRequestDTO(
            invitation_id=invitacion.id.value, user_id=invitado.id.value, action=accion
        )
    )


async def _inscripcion(uow, comp_id, jugador) -> Enrollment | None:
    async with uow:
        return await uow.enrollments.find_by_user_and_competition(jugador, comp_id)


# ======================================================================================
# P1: al cerrar, las pendientes esperan
# ======================================================================================


class TestP1AlCerrarEsperan:
    async def test_cerrar_a_mano_las_deja_en_espera_y_retira_su_aviso(self):
        """
        P1. Given una Ryder abierta con una invitación pendiente
        When el organizador cierra la inscripción
        Then la invitación queda ON_HOLD (no NO_ROOM) y su aviso de invitado se retira
        """
        uow, comp_id, organizador, _, _, _, invitacion = await _abierta_con_invitado()
        actividad = _Actividad()

        await _cierra(uow, comp_id, organizador, actividad)

        assert await _estado(uow, invitacion) is InvitationStatus.ON_HOLD
        [(retiradas,)] = actividad.de("invitations_closed")
        assert [i.id for i in retiradas] == [invitacion.id]

    async def test_la_caducada_queda_caducada(self):
        """P1. Given una pendiente ya caducada / When se cierra / Then EXPIRED, no ON_HOLD."""
        uow, comp_id, organizador, _, _, invitado, _ = await _abierta_con_invitado()
        caducada = await _invita(
            uow, comp_id, invitado, _expires_at=datetime.now() - timedelta(minutes=1)
        )

        await _cierra(uow, comp_id, organizador)

        assert await _estado(uow, caducada) is InvitationStatus.EXPIRED

    async def test_nombrar_capitanes_tambien_las_deja_en_espera(self):
        """
        P1. Given una Ryder abierta con una pendiente
        When el organizador nombra a los capitanes (eso cierra la inscripción)
        Then la invitación queda ON_HOLD
        """
        uow, comp_id, organizador, otro, _, _, invitacion = await _abierta_con_invitado()

        await NameCaptainsUseCase(uow).execute(
            NameCaptainsRequestDTO(
                competition_id=comp_id.value,
                team_a_captain_id=organizador.value,
                team_b_captain_id=otro.value,
            ),
            organizador,
        )

        assert await _estado(uow, invitacion) is InvitationStatus.ON_HOLD

    async def test_aceptar_una_en_espera_no_entra_y_lo_dice_con_su_codigo(self):
        """
        P1. Given una invitación ON_HOLD (inscripción cerrada)
        When el invitado la acepta
        Then INVITATION_ON_HOLD, sigue ON_HOLD y no se inscribe
        """
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)

        with pytest.raises(InvitationOnHoldViolation) as error:
            await _responde(usuarios, uow, invitacion, invitado, "ACCEPT")

        assert error.value.error_code == "INVITATION_ON_HOLD"
        assert str(error.value) == (
            "En lista de espera: la inscripción está cerrada. "
            "Si el organizador la reabre, podrás aceptarla."
        )
        assert await _estado(uow, invitacion) is InvitationStatus.ON_HOLD
        assert await _inscripcion(uow, comp_id, invitado.id) is None

    async def test_rechazar_una_en_espera_si(self):
        """P1. Given una ON_HOLD / When el invitado la rechaza / Then DECLINED."""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)

        respuesta = await _responde(usuarios, uow, invitacion, invitado, "DECLINE")

        assert respuesta.status == "DECLINED"
        assert await _estado(uow, invitacion) is InvitationStatus.DECLINED

    async def test_el_organizador_retira_una_en_espera(self):
        """P1. Given una ON_HOLD / When el organizador la retira / Then CANCELLED."""
        uow, comp_id, organizador, _, _, _, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)

        await CancelInvitationUseCase(uow).execute(invitacion.id.value, organizador.value)

        assert await _estado(uow, invitacion) is InvitationStatus.CANCELLED

    async def test_una_pendiente_colada_en_una_cerrada_pasa_a_espera_al_aceptarla(self):
        """
        P1. Given una invitación PENDING en una competición ya cerrada (de antes del cambio)
        When el invitado la acepta
        Then pasa a ON_HOLD, INVITATION_ON_HOLD, y no entra
        """
        uow, comp_id, organizador, _, usuarios, invitado, _ = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        colada = await _invita(uow, comp_id, invitado)

        with pytest.raises(InvitationOnHoldViolation):
            await _responde(usuarios, uow, colada, invitado, "ACCEPT")

        assert await _estado(uow, colada) is InvitationStatus.ON_HOLD
        assert await _inscripcion(uow, comp_id, invitado.id) is None

    async def test_el_invitado_sigue_viendo_la_competicion(self):
        """
        P1. Given una invitación ON_HOLD
        Then cuenta para ver la competición, pero la ficha no la ofrece para aceptar
        """
        uow, comp_id, organizador, _, _, invitado, _ = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)

        async with uow:
            visibles = await uow.invitations.competiciones_con_invitacion_pendiente(
                invitado.id, str(invitado.email), datetime.now()
            )
            ofrecida = await uow.invitations.pendiente_de(
                invitado.id, str(invitado.email), comp_id, datetime.now()
            )
        assert comp_id in visibles
        assert ofrecida is None


# ======================================================================================
# P2: al reabrir, vuelven
# ======================================================================================


class TestP2AlReabrirVuelven:
    async def test_reabrir_las_devuelve_a_pendientes_y_avisa_a_cada_uno(self):
        """
        P2. Given una invitación ON_HOLD
        When el organizador reabre
        Then vuelve a PENDING y su invitado recibe «ya puedes aceptar»
        """
        uow, comp_id, organizador, _, _, _, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        actividad = _Actividad()

        await _reabre(uow, comp_id, organizador, actividad)

        assert await _estado(uow, invitacion) is InvitationStatus.PENDING
        [(competicion, vuelven)] = actividad.de("invitations_acceptable_again")
        assert competicion.id == comp_id
        assert [i.id for i in vuelven] == [invitacion.id]

    async def test_reabierta_ya_se_acepta(self):
        """P2. Given reabierta / When el invitado acepta / Then entra (APPROVED)."""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        await _reabre(uow, comp_id, organizador)

        respuesta = await _responde(usuarios, uow, invitacion, invitado, "ACCEPT")

        assert respuesta.status == "ACCEPTED"
        assert (await _inscripcion(uow, comp_id, invitado.id)).status is (EnrollmentStatus.APPROVED)

    async def test_la_que_caduco_mientras_esperaba_queda_caducada_sin_aviso(self):
        """P2. Given una ON_HOLD que caducó / When se reabre / Then EXPIRED y sin aviso."""
        uow, comp_id, organizador, _, _, _, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        async with uow:
            esperando = await uow.invitations.find_by_id(invitacion.id)
            esperando._expires_at = datetime.now() - timedelta(minutes=1)
            await uow.invitations.update(esperando)
            await uow.commit()
        actividad = _Actividad()

        await _reabre(uow, comp_id, organizador, actividad)

        assert await _estado(uow, invitacion) is InvitationStatus.EXPIRED
        assert not any(vuelven for _, vuelven in actividad.de("invitations_acceptable_again"))

    async def test_al_reabrirse_sola_moviendo_el_torneo_r3_tambien(self):
        """
        P2 con R3. Given cerrada por el plazo con una invitación ON_HOLD
        When el organizador mueve el torneo y el plazo nuevo queda en el futuro
        Then se reabre sola, la invitación vuelve a PENDING y su invitado recibe el aviso
        """
        uow = InMemoryUnitOfWork()
        competition = await r3._cerrada(uow, por_el_plazo=True)
        _, invitado = await _usuarios()
        invitacion = await _invita(uow, competition.id, invitado)
        async with uow:
            esperando = await uow.invitations.find_by_id(invitacion.id)
            esperando.put_on_hold()
            await uow.invitations.update(esperando)
            await uow.commit()
        actividad = _Actividad()

        await UpdateCompetitionUseCase(
            uow,
            LocationBuilder(uow.countries),
            r3._Campos(),
            actividad=actividad,
            plazo=r3._plazo(r3.DESPUES),
        ).execute(competition.id, r3._fechas(7), competition.creator_id)

        assert await _estado(uow, invitacion) is InvitationStatus.PENDING
        [(_, vuelven)] = actividad.de("invitations_acceptable_again")
        assert [i.id for i in vuelven] == [invitacion.id]

    async def test_sin_ninguna_esperando_no_se_avisa(self):
        """P2. Given cerrada sin invitaciones en espera / When se reabre / Then ningún aviso."""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        await _responde(usuarios, uow, invitacion, invitado, "DECLINE")
        await _cierra(uow, comp_id, organizador)
        actividad = _Actividad()

        await _reabre(uow, comp_id, organizador, actividad)

        assert not any(vuelven for _, vuelven in actividad.de("invitations_acceptable_again"))


# ======================================================================================
# P3: al empezar o cancelar, sin plaza
# ======================================================================================


async def _cerrada_con_equipos_y_en_espera():
    """Una Ryder cerrada, con una sesión (se puede iniciar) y una invitación ON_HOLD."""
    uow, comp_id, *_ = await _montar()
    _, invitado = await _usuarios()
    invitacion = await _invita(uow, comp_id, invitado)
    async with uow:
        esperando = await uow.invitations.find_by_id(invitacion.id)
        esperando.put_on_hold()
        await uow.invitations.update(esperando)
        await uow.commit()
    async with uow:
        organizador = (await uow.competitions.find_by_id(comp_id)).creator_id
    return uow, comp_id, organizador, invitacion


class TestP3AlEmpezarOCancelarSinPlaza:
    async def test_iniciarla_las_deja_sin_plaza_y_se_avisa(self):
        """
        P3. Given una ON_HOLD en una cerrada
        When el organizador la inicia (IN_PROGRESS)
        Then la invitación pasa a NO_ROOM y el invitado recibe «no hubo plaza»
        """
        uow, comp_id, organizador, invitacion = await _cerrada_con_equipos_y_en_espera()
        actividad = _Actividad()

        await StartCompetitionUseCase(uow, actividad=actividad).execute(
            StartCompetitionRequestDTO(competition_id=comp_id.value), organizador
        )

        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM
        [(competicion, sin_plaza)] = actividad.de("invitations_no_place")
        assert competicion.id == comp_id
        assert [i.id for i in sin_plaza] == [invitacion.id]

    async def test_cancelarla_las_deja_sin_plaza_y_se_avisa(self):
        """P3. Given una ON_HOLD / When se cancela la competición / Then NO_ROOM y aviso."""
        uow, comp_id, organizador, invitacion = await _cerrada_con_equipos_y_en_espera()
        actividad = _Actividad()

        await CancelCompetitionUseCase(uow, actividad=actividad).execute(
            CancelCompetitionRequestDTO(competition_id=comp_id.value), organizador
        )

        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM
        [(competicion, sin_plaza)] = actividad.de("invitations_no_place")
        assert competicion.id == comp_id
        assert [i.id for i in sin_plaza] == [invitacion.id]

    async def test_por_el_primer_golpe_tambien(self):
        """
        P3. Given una ON_HOLD en una cerrada
        When el primer golpe la arranca (`cerrar_lo_pendiente`, lo que llaman los cuatro caminos)
        Then NO_ROOM
        """
        from src.modules.competition.application.services.solicitudes_al_empezar import (
            cerrar_lo_pendiente,
        )

        uow, comp_id, _, invitacion = await _cerrada_con_equipos_y_en_espera()

        async with uow:
            cerrado = await cerrar_lo_pendiente(uow, comp_id)
            await uow.commit()

        assert [i.id for i in cerrado.invitaciones] == [invitacion.id]
        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM


# ======================================================================================
# B1, B2: nadie entra sin su consentimiento
# ======================================================================================


class TestB1SinInscripcionAMano:
    async def test_no_hay_caso_de_uso(self):
        """B1. Then el caso de uso de inscribir a mano ya no existe."""
        assert (
            importlib.util.find_spec(
                "src.modules.competition.application.use_cases.direct_enroll_player_use_case"
            )
            is None
        )

    async def test_no_hay_ruta(self):
        """B1. Then la API no tiene `POST /competitions/{id}/enrollments/direct`."""
        from main import app

        rutas = set(app.openapi()["paths"])
        assert not any(r.endswith("/enrollments/direct") for r in rutas)
        assert any(r.endswith("/competitions/{competition_id}/enrollments") for r in rutas)


class TestB2NadieVuelveSinSuPermiso:
    @pytest.mark.parametrize("como", ["withdraw", "cancel"])
    async def test_aprobar_una_que_el_jugador_cerro_no(self, como):
        """
        B2. Given un jugador que se retiró (o canceló su solicitud)
        When el organizador intenta aprobarla
        Then no: sigue cerrada
        """
        uow = InMemoryUnitOfWork()
        organizador = UserId(uuid4())
        creada = await create_competition(uow, organizador)
        jugador = UserId(uuid4())
        if como == "withdraw":
            inscripcion = await create_approved_enrollment(uow, creada.id, jugador)
            inscripcion.withdraw()
        else:
            inscripcion = Enrollment.request(
                EnrollmentId.generate(), CompetitionId(creada.id), jugador
            )
            inscripcion.cancel()
        async with uow:
            await uow.enrollments.add(inscripcion)
            await uow.commit()

        with pytest.raises(EnrollmentStateError):
            await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO).execute(
                HandleEnrollmentRequestDTO(enrollment_id=inscripcion.id.value, action="APPROVE"),
                organizador,
            )

        assert (await _inscripcion(uow, CompetitionId(creada.id), jugador)).status is not (
            EnrollmentStatus.APPROVED
        )

    async def test_reabrir_no_inscribe_a_los_que_esperaban(self):
        """B2. Given una ON_HOLD / When se reabre / Then vuelve la invitación, no una inscripción."""
        uow, comp_id, organizador, _, _, invitado, _ = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)

        await _reabre(uow, comp_id, organizador)

        assert await _inscripcion(uow, comp_id, invitado.id) is None


# ======================================================================================
# B3: con los equipos formados
# ======================================================================================


async def _organizador_de(uow, comp_id) -> UserId:
    async with uow:
        return (await uow.competitions.find_by_id(comp_id)).creator_id


async def _equipos(uow, comp_id):
    async with uow:
        return await uow.team_assignments.find_by_competition(comp_id)


async def _con_la_sala_abierta(uow, comp_id) -> None:
    """Reabierta, sin reparto y con la sala de draft eligiendo."""
    async with uow:
        reparto = await uow.team_assignments.find_by_competition(comp_id)
        await uow.team_assignments.delete(reparto.id)
        await uow.drafts.delete_by_competition(comp_id)
        competicion = await uow.competitions.find_by_id(comp_id)
        await uow.drafts.add(
            Draft(
                id=DraftId.generate(),
                competition_id=comp_id,
                team_a_captain_id=competicion.ryder_cup.team_a_captain_id,
                team_b_captain_id=competicion.ryder_cup.team_b_captain_id,
                status=DraftStatus.IN_PROGRESS,
            )
        )
        await uow.commit()


def _por_id(uow, usuarios, comp_id, organizador, invitado):
    return SendInvitationByUserIdUseCase(uow, usuarios).execute(
        SendInvitationByUserIdRequestDTO(
            competition_id=comp_id.value,
            inviter_id=organizador.value,
            invitee_user_id=invitado.id.value,
        )
    )


def _por_correo(uow, usuarios, comp_id, organizador):
    return SendInvitationByEmailUseCase(uow, usuarios).execute(
        SendInvitationByEmailRequestDTO(
            competition_id=comp_id.value,
            inviter_id=organizador.value,
            invitee_email=f"nadie_{uuid4().hex[:6]}@example.com",
        )
    )


class TestB3ConLosEquiposFormados:
    async def test_sin_partidos_el_organizador_invita_por_id(self):
        """B3. Given equipos formados, sin partidos, reabierta / When invita / Then PENDING."""
        uow, comp_id, *_ = await _reabierta()
        usuarios, invitado = await _usuarios()

        invitacion = await _por_id(
            uow, usuarios, comp_id, await _organizador_de(uow, comp_id), invitado
        )

        assert invitacion.status == "PENDING"
        assert await _equipos(uow, comp_id) is not None

    async def test_sin_partidos_el_organizador_invita_por_correo(self):
        """B3. Given equipos formados, sin partidos / When invita por correo / Then PENDING."""
        uow, comp_id, *_ = await _reabierta()
        usuarios, _ = await _usuarios()

        invitacion = await _por_correo(uow, usuarios, comp_id, await _organizador_de(uow, comp_id))

        assert invitacion.status == "PENDING"

    async def test_al_aceptar_entra_se_deshacen_y_se_avisa_al_organizador(self):
        """
        B3. Given equipos formados, sin partidos, y una invitación pendiente
        When el invitado acepta
        Then entra, los equipos se deshacen y el organizador recibe «X ha entrado en Y:
        los equipos se han deshecho y hay que volver a formarlos»
        """
        uow, comp_id, *_ = await _reabierta()
        usuarios, invitado = await _usuarios()
        invitacion = await _invita(uow, comp_id, invitado)
        actividad = _Actividad()

        await _responde(usuarios, uow, invitacion, invitado, "ACCEPT", actividad)

        assert (await _inscripcion(uow, comp_id, invitado.id)).status is (EnrollmentStatus.APPROVED)
        assert await _equipos(uow, comp_id) is None
        [(competicion, inscripcion)] = actividad.de("teams_undone_by_entry")
        assert competicion.id == comp_id
        assert inscripcion.user_id == invitado.id

    async def test_sin_equipos_aceptar_no_avisa_de_nada_deshecho(self):
        """B3. Given sin equipos formados / When acepta / Then entra y sin ese aviso."""
        uow, _, _, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        actividad = _Actividad()

        await _responde(usuarios, uow, invitacion, invitado, "ACCEPT", actividad)

        assert actividad.de("teams_undone_by_entry") == []

    async def test_con_partidos_no_se_invita(self):
        """B3. Given equipos formados y partidos / When invita / Then TEAMS_FORMED."""
        uow, comp_id, round_id, equipo_a, equipo_b = await _reabierta()
        await _con_partidos(uow, round_id, equipo_a, equipo_b)
        usuarios, invitado = await _usuarios()
        organizador = await _organizador_de(uow, comp_id)

        with pytest.raises(TeamsFormedError):
            await _por_id(uow, usuarios, comp_id, organizador, invitado)
        with pytest.raises(TeamsFormedError):
            await _por_correo(uow, usuarios, comp_id, organizador)

    async def test_con_partidos_no_se_acepta(self):
        """B3. Given equipos formados y partidos / When acepta / Then TEAMS_FORMED, PENDING."""
        uow, comp_id, round_id, equipo_a, equipo_b = await _reabierta()
        usuarios, invitado = await _usuarios()
        invitacion = await _invita(uow, comp_id, invitado)
        await _con_partidos(uow, round_id, equipo_a, equipo_b)

        with pytest.raises(TeamsFormedError):
            await _responde(usuarios, uow, invitacion, invitado, "ACCEPT")

        assert await _estado(uow, invitacion) is InvitationStatus.PENDING
        assert await _inscripcion(uow, comp_id, invitado.id) is None
        assert await _equipos(uow, comp_id) is not None

    async def test_con_la_sala_de_draft_abierta_no_se_invita(self):
        """B3. Given la sala de draft eligiendo / When invita / Then DRAFT_IN_PROGRESS."""
        uow, comp_id, *_ = await _reabierta()
        await _con_la_sala_abierta(uow, comp_id)
        usuarios, invitado = await _usuarios()
        organizador = await _organizador_de(uow, comp_id)

        with pytest.raises(DraftInProgressError):
            await _por_id(uow, usuarios, comp_id, organizador, invitado)
        with pytest.raises(DraftInProgressError):
            await _por_correo(uow, usuarios, comp_id, organizador)

    async def test_con_la_sala_de_draft_abierta_no_se_acepta(self):
        """B3. Given la sala de draft eligiendo / When acepta / Then DRAFT_IN_PROGRESS."""
        uow, comp_id, *_ = await _reabierta()
        usuarios, invitado = await _usuarios()
        invitacion = await _invita(uow, comp_id, invitado)
        await _con_la_sala_abierta(uow, comp_id)

        with pytest.raises(DraftInProgressError):
            await _responde(usuarios, uow, invitacion, invitado, "ACCEPT")

        assert await _estado(uow, invitacion) is InvitationStatus.PENDING
        assert await _inscripcion(uow, comp_id, invitado.id) is None


# ======================================================================================
# B4: la RFEG para quien entra tarde
# ======================================================================================


class TestB4LaRfegAlVolverACerrar:
    async def test_reabierta_entra_uno_y_al_volver_a_cerrar_se_lanza_otra(self):
        """
        B4. Given cerrada (con su actualización de la RFEG) y reabierta
        When entra un invitado y se vuelve a cerrar
        Then se lanza otra actualización, que es de toda la competición (también el nuevo)
        """
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        lanzador = MagicMock()
        await _cierra(uow, comp_id, organizador, lanzador=lanzador)
        await _reabre(uow, comp_id, organizador)
        await _responde(usuarios, uow, invitacion, invitado, "ACCEPT")

        await _cierra(uow, comp_id, organizador, lanzador=lanzador)

        assert lanzador.lanzar.call_count == 2
        primera, segunda = (c.args[0] for c in lanzador.lanzar.call_args_list)
        assert primera != segunda
        async with uow:
            ultima = await uow.handicap_updates.ultima_de(comp_id)
            competicion = await uow.competitions.find_by_id(comp_id)
        assert ultima.id == segunda
        assert ultima.competition_id == comp_id
        assert competicion.status is CompetitionStatus.CLOSED


# ======================================================================================
# Lo que se guarda y a quién se avisa
# ======================================================================================


async def _con_espia(uow) -> AsyncMock:
    espia = AsyncMock(wraps=uow.invitations.update)
    uow.invitations.update = espia
    return espia


def _actualizadas(espia: AsyncMock) -> list:
    return [c.args[0].id for c in espia.call_args_list]


class TestSeGuardaCadaUna:
    """Con la base de datos, lo que no se guarda no pasa: cada cambio, con su `update`."""

    async def test_al_cerrar(self):
        uow, comp_id, _, _, _, invitado, invitacion = await _abierta_con_invitado()
        caducada = await _invita(
            uow, comp_id, invitado, _expires_at=datetime.now() - timedelta(minutes=1)
        )
        espia = await _con_espia(uow)

        async with uow:
            await en_espera_las_pendientes(uow, comp_id)

        assert sorted(map(str, _actualizadas(espia))) == sorted(
            map(str, [invitacion.id, caducada.id])
        )

    async def test_al_reabrir_tambien_la_que_caduco(self):
        uow, comp_id, organizador, _, _, _, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id))._expires_at = (
                datetime.now() - timedelta(minutes=1)
            )
        espia = await _con_espia(uow)

        async with uow:
            vuelven = await vuelven_las_que_esperan(uow, comp_id)

        assert vuelven == []
        assert _actualizadas(espia) == [invitacion.id]

    async def test_al_empezar_tambien_la_que_caduco(self):
        uow, comp_id, _, invitacion = await _cerrada_con_equipos_y_en_espera()
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id))._expires_at = (
                datetime.now() - timedelta(minutes=1)
            )
        espia = await _con_espia(uow)

        async with uow:
            sin_plaza = await sin_plaza_para_las_que_esperan(uow, comp_id)

        # Caducada, no sin plaza: se quedó sin respuesta
        assert sin_plaza == []
        assert await _estado(uow, invitacion) is InvitationStatus.EXPIRED
        assert _actualizadas(espia) == [invitacion.id]

    async def test_al_empezar_la_que_espera(self):
        uow, comp_id, _, invitacion = await _cerrada_con_equipos_y_en_espera()
        espia = await _con_espia(uow)

        async with uow:
            await sin_plaza_para_las_que_esperan(uow, comp_id)

        assert _actualizadas(espia) == [invitacion.id]


class TestResponderUnaEnEsperaCaducada:
    async def test_se_caduca_y_se_retira_su_aviso(self):
        """P1. Given ON_HOLD caducada / When el invitado la rechaza / Then EXPIRED y retirada."""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id))._expires_at = (
                datetime.now() - timedelta(minutes=1)
            )
        actividad = _Actividad()

        with pytest.raises(InvalidInvitationStatusViolation):
            await _responde(usuarios, uow, invitacion, invitado, "DECLINE", actividad)

        assert await _estado(uow, invitacion) is InvitationStatus.EXPIRED
        [(cerradas,)] = actividad.de("invitations_closed")
        assert [i.id for i in cerradas] == [invitacion.id]


class TestLosAvisosSoloAQuienTieneCuenta:
    async def _dos(self):
        """Una invitación a un usuario y otra a un correo sin cuenta, en una competición."""
        uow, comp_id, _, _, _, _, con_cuenta = await _abierta_con_invitado()
        async with uow:
            competicion = await uow.competitions.find_by_id(comp_id)
        sin_cuenta = Invitation.create(
            id=InvitationId.generate(),
            competition_id=comp_id,
            inviter_id=competicion.creator_id,
            invitee_email="nadie@example.com",
        )
        return competicion, con_cuenta, sin_cuenta

    @pytest.mark.parametrize("aviso", ["invitations_acceptable_again", "invitations_no_place"])
    async def test_sin_cuenta_no_se_avisa(self, aviso):
        competicion, con_cuenta, sin_cuenta = await self._dos()
        actividad = _Actividad()

        await getattr(AvisosDeActividad(actividad), aviso)(competicion, [con_cuenta, sin_cuenta])

        [(_, avisadas)] = actividad.de(aviso)
        assert [i.id for i in avisadas] == [con_cuenta.id]

    @pytest.mark.parametrize("aviso", ["invitations_acceptable_again", "invitations_no_place"])
    async def test_sin_nadie_con_cuenta_no_se_llama(self, aviso):
        competicion, _, sin_cuenta = await self._dos()
        actividad = _Actividad()

        await getattr(AvisosDeActividad(actividad), aviso)(competicion, [sin_cuenta])

        assert actividad.avisos == []
