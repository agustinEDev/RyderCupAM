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
| P1   | pasan los 7 días esperando                                  | no caduca: sigue ON_HOLD, se puede rechazar    |
| P2   | el organizador reabre                                       | ON_HOLD → PENDING con 7 días nuevos, aviso «ya |
|      | (también la que llevaba más de 7 días esperando)            | puedes aceptar» a cada invitado con cuenta     |
| P2   | se reabre sola al mover el torneo (R3)                      | igual que al reabrir                           |
| P2   | invitado solo por correo, sin cuenta                        | al reabrir se le reenvía el correo de siempre, |
|      |                                                             | con la caducidad nueva                         |
| O1   | se reabre una Ryder con partidos ya generados               | las ON_HOLD → NO_ROOM, «no hubo plaza»         |
| O1   | se intenta reabrir con la sala de draft abierta             | DRAFT_IN_PROGRESS: se acaba antes el draft     |
| C1   | se llena estando cerrada (última plaza)                     | también las ON_HOLD → NO_ROOM, «no hubo plaza» |
| C1   | se reabre con al menos una plaza libre                      | vuelven TODAS (aviso y correo); entra quien    |
|      |                                                             | antes acepte, y al llenarse las demás NO_ROOM  |
| C1   | se reabre sin ninguna plaza libre                           | todas NO_ROOM con «no hubo plaza»              |
| C2   | al reabrir, el invitado ya está inscrito (APPROVED)         | se retira su invitación, sin aviso; con una    |
|      |                                                             | solicitud sin aprobar, no: vuelve              |
| O1   | se mueven las fechas con la sala de draft abierta (R3)      | DRAFT_IN_PROGRESS antes de mover nada          |
| D1   | se vuelve a invitar a quien tiene una ON_HOLD               | INVITATION_ON_HOLD_EXISTS                      |
| D1   | se acepta: el estado de la competición se lee bloqueado     | contra la carrera con reabrir                  |
| P3   | empieza (a mano o por el primer golpe) o se cancela         | ON_HOLD → NO_ROOM, aviso «no hubo plaza»       |
| P3   | se cancela con la inscripción abierta                       | también las PENDING → NO_ROOM, su aviso de     |
|      |                                                             | invitado se retira y «no hubo plaza»           |
| B1   | el organizador inscribe a mano                              | ya no existe: ni ruta, ni caso de uso          |
| B2   | aprobar una inscripción que el jugador cerró                | no: solo se aprueba lo que él pidió            |
| B3   | equipos formados, sin partidos: el organizador invita       | puede (por id y por correo)                    |
| B3   | ... el invitado acepta                                      | entra, equipos deshechos, aviso al organizador |
| B3   | con partidos: invitar o aceptar                             | TEAMS_FORMED                                   |
| B3   | con la sala de draft abierta: invitar, aceptar, aprobar o   | DRAFT_IN_PROGRESS: nadie entra durante el      |
|      | apuntarse a una pública                                     | draft                                          |
| B3   | el organizador vuelve a formar los equipos (a mano o draft) | se retira el aviso de equipos deshechos        |
| B4   | reabierta, entra uno y se vuelve a cerrar                   | otra actualización de la RFEG, para todos      |
"""

import importlib.util
import logging
from datetime import datetime, time, timedelta
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
from src.modules.competition.application.dto.enrollment_dto import (
    HandleEnrollmentRequestDTO,
    RequestEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.dto.round_match_dto import AssignTeamsRequestDTO
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.baja_de_la_competicion import (
    DraftInProgressError,
)
from src.modules.competition.application.services.equipos_formados import TeamsFormedError
from src.modules.competition.application.services.invitacion_que_impide import pendiente_vigente
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    al_reabrir,
    en_espera_las_pendientes,
    sin_plaza_para_las_que_esperan,
)
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
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
from src.modules.competition.application.use_cases.make_draft_pick_use_case import (
    MakeDraftPickUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
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
from src.modules.competition.application.use_cases.start_draft_use_case import (
    StartDraftUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.entities.enrollment import Enrollment, EnrollmentStateError
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    InvitationOnHoldExistsViolation,
    InvitationOnHoldViolation,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.draft_id import DraftId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.visibility import Visibility
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

    async def test_la_que_llevaba_mas_de_7_dias_vuelve_con_7_dias_nuevos(self):
        """
        P2. Given una ON_HOLD cuyo plazo de 7 días ya pasó (esperando no caduca)
        When se reabre / Then PENDING, caduca dentro de 7 días y se avisa
        """
        uow, comp_id, organizador, _, _, _, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        async with uow:
            esperando = await uow.invitations.find_by_id(invitacion.id)
            esperando._expires_at = datetime.now() - timedelta(minutes=1)
            await uow.invitations.update(esperando)
            await uow.commit()
        actividad = _Actividad()

        antes = datetime.now()
        await _reabre(uow, comp_id, organizador, actividad)

        async with uow:
            vuelta = await uow.invitations.find_by_id(invitacion.id)
        assert vuelta.status is InvitationStatus.PENDING
        assert antes + timedelta(days=7) <= vuelta.expires_at
        assert vuelta.expires_at <= datetime.now() + timedelta(days=7)
        [(_, vuelven)] = actividad.de("invitations_acceptable_again")
        assert [i.id for i in vuelven] == [invitacion.id]

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

    async def test_al_reabrir_tambien_la_que_paso_de_7_dias(self):
        uow, comp_id, organizador, _, _, _, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id))._expires_at = (
                datetime.now() - timedelta(minutes=1)
            )
        espia = await _con_espia(uow)

        async with uow:
            esperan = [await uow.invitations.find_by_id(invitacion.id)]
            vuelven = (await al_reabrir(uow, comp_id, esperan, sin_sitio=False)).vuelven

        assert [i.id for i in vuelven] == [invitacion.id]
        assert _actualizadas(espia) == [invitacion.id]

    async def test_al_empezar_tambien_la_que_paso_de_7_dias(self):
        uow, comp_id, _, invitacion = await _cerrada_con_equipos_y_en_espera()
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id))._expires_at = (
                datetime.now() - timedelta(minutes=1)
            )
        espia = await _con_espia(uow)

        async with uow:
            sin_plaza = await sin_plaza_para_las_que_esperan(uow, comp_id)

        # Esperando no caduca: sin plaza
        assert [i.id for i in sin_plaza] == [invitacion.id]
        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM
        assert _actualizadas(espia) == [invitacion.id]

    async def test_al_empezar_la_que_espera(self):
        uow, comp_id, _, invitacion = await _cerrada_con_equipos_y_en_espera()
        espia = await _con_espia(uow)

        async with uow:
            await sin_plaza_para_las_que_esperan(uow, comp_id)

        assert _actualizadas(espia) == [invitacion.id]


class TestEsperandoNoCaduca:
    async def test_pasados_los_7_dias_se_puede_rechazar(self):
        """P1. Given ON_HOLD con el plazo de 7 días pasado / When la rechaza / Then DECLINED."""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id))._expires_at = (
                datetime.now() - timedelta(minutes=1)
            )
        actividad = _Actividad()

        respuesta = await _responde(usuarios, uow, invitacion, invitado, "DECLINE", actividad)

        assert respuesta.status == "DECLINED"
        assert actividad.de("invitations_closed") == []

    async def test_pasados_los_7_dias_sigue_en_espera_y_visible(self):
        """P1. Given ON_HOLD con el plazo pasado / Then sigue ON_HOLD y el invitado la ve."""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id))._expires_at = (
                datetime.now() - timedelta(minutes=1)
            )

        with pytest.raises(InvitationOnHoldViolation):
            await _responde(usuarios, uow, invitacion, invitado, "ACCEPT")

        assert await _estado(uow, invitacion) is InvitationStatus.ON_HOLD
        async with uow:
            visibles = await uow.invitations.competiciones_con_invitacion_pendiente(
                invitado.id, None, datetime.now()
            )
        assert comp_id in visibles


class TestP3CancelarAbierta:
    async def test_las_pendientes_se_quedan_sin_plaza_y_se_avisa(self):
        """
        P3. Given una competición ABIERTA con una invitación pendiente (y otra caducada)
        When se cancela
        Then la pendiente pasa a NO_ROOM, su aviso de invitado se retira y le llega
        «no hubo plaza»; la caducada, EXPIRED
        """
        uow, comp_id, organizador, _, _, invitado, invitacion = await _abierta_con_invitado()
        caducada = await _invita(
            uow, comp_id, invitado, _expires_at=datetime.now() - timedelta(minutes=1)
        )
        actividad = _Actividad()

        await CancelCompetitionUseCase(uow, actividad=actividad).execute(
            CancelCompetitionRequestDTO(competition_id=comp_id.value), organizador
        )

        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM
        assert await _estado(uow, caducada) is InvitationStatus.EXPIRED
        [(_, sin_plaza)] = actividad.de("invitations_no_place")
        assert [i.id for i in sin_plaza] == [invitacion.id]
        [(cerradas,)] = actividad.de("invitations_closed")
        assert sorted(str(i.id) for i in cerradas) == sorted([str(invitacion.id), str(caducada.id)])

    async def test_se_guarda_cada_una(self):
        """P3. Given abierta, una pendiente y una caducada / When se cancela / Then las dos,
        guardadas."""
        uow, comp_id, organizador, _, _, invitado, invitacion = await _abierta_con_invitado()
        caducada = await _invita(
            uow, comp_id, invitado, _expires_at=datetime.now() - timedelta(minutes=1)
        )
        espia = await _con_espia(uow)

        await CancelCompetitionUseCase(uow).execute(
            CancelCompetitionRequestDTO(competition_id=comp_id.value), organizador
        )

        assert sorted(map(str, _actualizadas(espia))) == sorted(
            map(str, [invitacion.id, caducada.id])
        )


class TestNadieEntraDuranteElDraft:
    async def test_aprobar_una_solicitud_no(self):
        """B3. Given la sala de draft eligiendo / When se aprueba una solicitud / Then no."""
        uow, comp_id, *_ = await _reabierta()
        await _con_la_sala_abierta(uow, comp_id)
        solicitud = Enrollment.request(EnrollmentId.generate(), comp_id, UserId(uuid4()))
        async with uow:
            await uow.enrollments.add(solicitud)
            await uow.commit()

        with pytest.raises(DraftInProgressError):
            await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO).execute(
                HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
                await _organizador_de(uow, comp_id),
            )

        assert (await _inscripcion(uow, comp_id, solicitud.user_id)).status is (
            EnrollmentStatus.REQUESTED
        )

    async def test_apuntarse_a_una_publica_no(self):
        """B3. Given una pública con la sala de draft eligiendo / When se apunta / Then no."""
        uow, comp_id, *_ = await _reabierta(publica=True)
        await _con_la_sala_abierta(uow, comp_id)
        jugador = UserId(uuid4())

        with pytest.raises(DraftInProgressError):
            await RequestEnrollmentUseCase(uow, USUARIOS_CON_GENERO).execute(
                RequestEnrollmentRequestDTO(competition_id=comp_id.value, user_id=jugador.value)
            )

        assert await _inscripcion(uow, comp_id, jugador) is None


class TestAlVolverAFormarLosEquipos:
    async def test_a_mano_se_retira_el_aviso_de_equipos_deshechos(self):
        """B3. Given deshechos al entrar uno / When el organizador los forma / Then se retira."""
        uow, comp_id, *_ = await _reabierta()
        usuarios, invitado = await _usuarios()
        invitacion = await _invita(uow, comp_id, invitado)
        await _responde(usuarios, uow, invitacion, invitado, "ACCEPT")
        organizador = await _organizador_de(uow, comp_id)
        await _cierra(uow, comp_id, organizador)
        async with uow:
            aprobados = await uow.enrollments.find_by_competition_and_status(
                comp_id, EnrollmentStatus.APPROVED
            )
        # Impares no se reparten: fuera uno que no es capitán
        if len(aprobados) % 2:
            await create_approved_enrollment(uow, comp_id.value, UserId(uuid4()))
        actividad = _Actividad()

        await AssignTeamsUseCase(uow, USUARIOS_CON_GENERO, actividad=actividad).execute(
            AssignTeamsRequestDTO(competition_id=comp_id.value, mode="AUTOMATIC"), organizador
        )

        [(competicion,)] = actividad.de("teams_formed")
        assert competicion.id == comp_id

    async def test_sin_formarlos_no_se_retira(self):
        """B3. Given formar los equipos falla / Then no se retira nada."""
        uow, comp_id, *_ = await _reabierta()
        actividad = _Actividad()

        with pytest.raises(Exception):
            await AssignTeamsUseCase(uow, USUARIOS_CON_GENERO, actividad=actividad).execute(
                AssignTeamsRequestDTO(competition_id=comp_id.value, mode="AUTOMATIC"),
                await _organizador_de(uow, comp_id),
            )

        assert actividad.de("teams_formed") == []

    async def test_al_acabar_el_draft_se_retira(self):
        """B3. Given la sala con un último turno / When el capitán elige / Then se retira."""
        uow, comp_id, *_ = await _reabierta()
        organizador = await _organizador_de(uow, comp_id)
        async with uow:
            reparto = await uow.team_assignments.find_by_competition(comp_id)
            await uow.team_assignments.delete(reparto.id)
            await uow.drafts.delete_by_competition(comp_id)
            await uow.commit()
        await _cierra(uow, comp_id, organizador)
        actividad = _Actividad()
        sala = await StartDraftUseCase(
            uow, USUARIOS_CON_GENERO, sorteo=lambda: "A", actividad=actividad
        ).execute(comp_id.value, organizador)
        assert actividad.de("teams_formed") == []

        # Eligen por turnos hasta que la sala termina
        while sala.status != "COMPLETED":
            async with uow:
                draft = await uow.drafts.find_by_competition(comp_id)
            capitan = (
                draft.team_a_captain_id if draft.current_team == "A" else draft.team_b_captain_id
            )
            sala = await MakeDraftPickUseCase(
                uow, USUARIOS_CON_GENERO, actividad=actividad
            ).execute(comp_id.value, capitan, sala.available_players[0].user_id)

        [(competicion,)] = actividad.de("teams_formed")
        assert competicion.id == comp_id


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


# ======================================================================================
# Decisiones del 15 nov por la tarde (O1, O2, C1, C2) y revisiones (D1, D2)
# ======================================================================================


class _Correos:
    def __init__(self):
        self.enviados: list[dict] = []

    async def send_invitation_email(self, **datos) -> bool:
        self.enviados.append(datos)
        return True


async def _en_espera(uow, comp_id, invitado=None, **mas) -> Invitation:
    """Una invitación ya en espera, a una cuenta o (sin `invitado`) a un correo sin cuenta."""
    async with uow:
        organizador = (await uow.competitions.find_by_id(comp_id)).creator_id
        invitacion = Invitation.create(
            id=InvitationId.generate(),
            competition_id=comp_id,
            inviter_id=organizador,
            invitee_email=str(invitado.email) if invitado else f"sin_{uuid4().hex[:6]}@x.com",
            invitee_user_id=invitado.id if invitado else None,
        )
        for campo, valor in mas.items():
            setattr(invitacion, campo, valor)
        invitacion.put_on_hold()
        await uow.invitations.add(invitacion)
        await uow.commit()
    return invitacion


async def _cerrada_ryder():
    """Una Ryder cerrada con equipos (sin partidos), su organizador y lo de sus partidos."""
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
    return uow, comp_id, await _organizador_de(uow, comp_id), (round_id, equipo_a, equipo_b)


async def _con_cupo(uow, comp_id, plazas: int) -> None:
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion._max_players = plazas
        await uow.competitions.update(competicion)
        await uow.commit()


class TestO1RyderConPartidosODraft:
    async def test_con_partidos_al_reabrir_se_quedan_sin_plaza(self):
        """O1. Given Ryder cerrada con partidos y una ON_HOLD / When se reabre / Then NO_ROOM y
        «no hubo plaza»; ningún «ya puedes aceptar»"""
        uow, comp_id, organizador, (round_id, equipo_a, equipo_b) = await _cerrada_ryder()
        await _con_partidos(uow, round_id, equipo_a, equipo_b)
        _, invitado = await _usuarios()
        invitacion = await _en_espera(uow, comp_id, invitado)
        actividad = _Actividad()

        await _reabre(uow, comp_id, organizador, actividad)

        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM
        [(_, sin_plaza)] = actividad.de("invitations_no_place")
        assert [i.id for i in sin_plaza] == [invitacion.id]
        assert not any(v for _, v in actividad.de("invitations_acceptable_again"))

    async def test_con_la_sala_de_draft_abierta_no_se_reabre(self):
        """O1. Given la sala de draft eligiendo / When se reabre / Then DRAFT_IN_PROGRESS y
        sigue cerrada, con la invitación en espera"""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        await _con_la_sala_abierta(uow, comp_id)
        _, invitado = await _usuarios()
        invitacion = await _en_espera(uow, comp_id, invitado)

        with pytest.raises(DraftInProgressError):
            await _reabre(uow, comp_id, organizador)

        async with uow:
            competicion = await uow.competitions.find_by_id(comp_id)
        assert competicion.status is CompetitionStatus.CLOSED
        assert await _estado(uow, invitacion) is InvitationStatus.ON_HOLD


class TestO2CorreoAlReabrir:
    async def test_sin_cuenta_se_le_reenvia_el_correo_con_la_caducidad_nueva(self):
        """O2. Given una ON_HOLD a un correo sin cuenta y otra a una cuenta / When se reabre
        / Then el correo de invitación de siempre, solo al de sin cuenta, con la nueva fecha"""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        _, invitado = await _usuarios()
        con_cuenta = await _en_espera(uow, comp_id, invitado)
        sin_cuenta = await _en_espera(
            uow, comp_id, _personal_message="Ven", _expires_at=datetime.now() - timedelta(days=1)
        )
        correos = _Correos()

        await ReopenEnrollmentsUseCase(uow, correos=correos, user_uow=UsuariosEnMemoria()).execute(
            ReopenEnrollmentsRequestDTO(competition_id=comp_id.value), organizador
        )

        async with uow:
            vuelta = await uow.invitations.find_by_id(sin_cuenta.id)
        [enviado] = correos.enviados
        assert enviado["to_email"] == sin_cuenta.invitee_email
        assert enviado["expires_at"] == vuelta.expires_at
        assert vuelta.expires_at > datetime.now()
        assert enviado["personal_message"] == "Ven"
        assert enviado["competition_name"] == "Test Cup"
        assert enviado["invitee_name"] is None
        assert enviado["inviter_name"] == "Unknown"
        assert await _estado(uow, con_cuenta) is InvitationStatus.PENDING

    async def test_si_el_correo_falla_la_reapertura_sigue(self):
        """O2. Given el correo falla / When se reabre / Then reabierta igual."""

        class _Rotos:
            async def send_invitation_email(self, **_datos) -> bool:
                raise RuntimeError("caido")

        uow, comp_id, organizador, _ = await _cerrada_ryder()
        sin_cuenta = await _en_espera(uow, comp_id)

        await ReopenEnrollmentsUseCase(uow, correos=_Rotos(), user_uow=UsuariosEnMemoria()).execute(
            ReopenEnrollmentsRequestDTO(competition_id=comp_id.value), organizador
        )

        assert await _estado(uow, sin_cuenta) is InvitationStatus.PENDING

    async def test_sin_servicio_de_correo_no_se_intenta(self, caplog):
        """O2. Given sin servicio de correo (fuera de producción) / When se reabre / Then
        ni se intenta: ningún aviso de correo fallido"""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        await _en_espera(uow, comp_id)

        with caplog.at_level(logging.WARNING):
            await _reabre(uow, comp_id, organizador)

        assert "resend" not in caplog.text

    async def test_el_nombre_de_quien_invita_es_el_suyo(self):
        """O2. Given quien invita existe / Then el correo lleva su nombre, como al invitar."""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        usuarios = UsuariosEnMemoria()
        org = User.create(
            first_name="Olga",
            last_name="Ruiz",
            email_str=f"olga_{uuid4().hex[:6]}@example.com",
            plain_password="SecureP@ssw0rd123",
        )
        org.update_profile(alias="Olguita")
        async with usuarios:
            await usuarios.users.save(org)
            await usuarios.commit()
        await _en_espera(uow, comp_id, _inviter_id=org.id)
        correos = _Correos()

        await ReopenEnrollmentsUseCase(uow, correos=correos, user_uow=usuarios).execute(
            ReopenEnrollmentsRequestDTO(competition_id=comp_id.value), organizador
        )

        [enviado] = correos.enviados
        # No está inscrito en ella, así que no pidió su nombre legal: el de siempre
        assert enviado["inviter_name"] == "Olguita"


class TestC1Cupo:
    async def test_al_llenarse_cerrada_tambien_las_que_esperan(self):
        """C1. Given cerrada con una ON_HOLD / When se ocupa la última plaza / Then NO_ROOM."""
        from src.modules.competition.application.services.invitaciones_al_cerrar import (
            al_ocupar_una_plaza,
        )

        uow, comp_id, _, _ = await _cerrada_ryder()
        _, invitado = await _usuarios()
        invitacion = await _en_espera(uow, comp_id, invitado)

        async with uow:
            llena = await al_ocupar_una_plaza(uow, comp_id, 23, 24)
            await uow.commit()

        assert [i.id for i in llena.cerradas] == [invitacion.id]
        assert [i.id for i in llena.esperaban] == [invitacion.id]
        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM

    async def test_al_llenarse_cerrada_al_aprobar_se_avisa_de_que_no_hubo_plaza(self):
        """C1. Given cerrada con una plaza, una solicitud y una ON_HOLD / When se aprueba la
        solicitud / Then la invitación, NO_ROOM y «no hubo plaza»"""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        await _con_cupo(uow, comp_id, 5)
        solicitud = Enrollment.request(EnrollmentId.generate(), comp_id, UserId(uuid4()))
        async with uow:
            await uow.enrollments.add(solicitud)
            await uow.commit()
        _, invitado = await _usuarios()
        invitacion = await _en_espera(uow, comp_id, invitado)
        actividad = _Actividad()

        await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO, actividad=actividad).execute(
            HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
            organizador,
        )

        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM
        [(_, sin_plaza)] = actividad.de("invitations_no_place")
        assert [i.id for i in sin_plaza] == [invitacion.id]

    async def test_con_una_plaza_libre_vuelven_todas_y_entra_quien_antes_acepte(self):
        """C1. Given una plaza libre y dos ON_HOLD / When se reabre / Then vuelven las dos,
        con su aviso; acepta una y la otra se queda sin plaza (BE #359)"""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        await _con_cupo(uow, comp_id, 5)  # 4 inscritos: queda una
        usuarios_uno, uno = await _usuarios()
        _, otro = await _usuarios()
        primera = await _en_espera(uow, comp_id, uno)
        segunda = await _en_espera(uow, comp_id, otro)
        actividad = _Actividad()

        await _reabre(uow, comp_id, organizador, actividad)

        assert await _estado(uow, primera) is InvitationStatus.PENDING
        assert await _estado(uow, segunda) is InvitationStatus.PENDING
        [(_, vuelven)] = actividad.de("invitations_acceptable_again")
        assert sorted(str(i.id) for i in vuelven) == sorted([str(primera.id), str(segunda.id)])
        assert not any(v for _, v in actividad.de("invitations_no_place"))

        await _responde(usuarios_uno, uow, primera, uno, "ACCEPT")

        assert await _estado(uow, segunda) is InvitationStatus.NO_ROOM

    async def test_con_franjas_el_maximo_no_cuenta(self):
        """C1. Given el máximo lleno pero con franjas (el cupo son sus plazas) / When se
        reabre / Then vuelve"""
        uow, comp_id, organizador, (round_id, _, _) = await _cerrada_ryder()
        await _con_cupo(uow, comp_id, 4)
        async with uow:
            sesion = await uow.rounds.find_by_id(round_id)
            sesion._hoja_de_salidas = HojaDeSalidas(time(9, 0), time(10, 0), 10, 4)
            await uow.rounds.update(sesion)
            await uow.commit()
        _, invitado = await _usuarios()
        invitacion = await _en_espera(uow, comp_id, invitado)

        await _reabre(uow, comp_id, organizador)

        assert await _estado(uow, invitacion) is InvitationStatus.PENDING

    async def test_llena_al_reabrir_ninguna_vuelve(self):
        """C1. Given llena / When se reabre / Then ningún «ya puedes aceptar»."""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        await _con_cupo(uow, comp_id, 4)
        _, invitado = await _usuarios()
        invitacion = await _en_espera(uow, comp_id, invitado)
        actividad = _Actividad()

        await _reabre(uow, comp_id, organizador, actividad)

        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM
        assert not any(v for _, v in actividad.de("invitations_acceptable_again"))


class TestC2YaInscrito:
    async def test_se_retira_sin_aviso(self):
        """C2. Given una ON_HOLD de quien ya está inscrito / When se reabre / Then CANCELLED,
        sin «ya puedes aceptar» ni «no hubo plaza»"""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        _, invitado = await _usuarios()
        await create_approved_enrollment(uow, comp_id.value, invitado.id)
        invitacion = await _en_espera(uow, comp_id, invitado)
        actividad = _Actividad()

        await _reabre(uow, comp_id, organizador, actividad)

        assert await _estado(uow, invitacion) is InvitationStatus.CANCELLED
        assert not any(v for _, v in actividad.de("invitations_acceptable_again"))
        assert not any(v for _, v in actividad.de("invitations_no_place"))

    async def test_una_solicitud_sin_aprobar_no_cuenta(self):
        """C2. Given una ON_HOLD de quien tiene una solicitud vieja sin aprobar / When se
        reabre / Then vuelve: solo cuenta estar inscrito"""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        _, invitado = await _usuarios()
        async with uow:
            await uow.enrollments.add(
                Enrollment.request(EnrollmentId.generate(), comp_id, invitado.id)
            )
            await uow.commit()
        invitacion = await _en_espera(uow, comp_id, invitado)

        await _reabre(uow, comp_id, organizador)

        assert await _estado(uow, invitacion) is InvitationStatus.PENDING

    async def test_una_inscripcion_cerrada_no_cuenta(self):
        """C2. Given una ON_HOLD de quien se retiró / When se reabre / Then vuelve, con aviso."""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        _, invitado = await _usuarios()
        vieja = await create_approved_enrollment(uow, comp_id.value, invitado.id)
        async with uow:
            vieja.withdraw()
            await uow.enrollments.update(vieja)
            await uow.commit()
        invitacion = await _en_espera(uow, comp_id, invitado)
        actividad = _Actividad()

        await _reabre(uow, comp_id, organizador, actividad)

        assert await _estado(uow, invitacion) is InvitationStatus.PENDING


class TestD1Carreras:
    async def test_aceptar_lee_la_competicion_bloqueada_en_la_primera_fase(self):
        """D1. Given una ON_HOLD / When se acepta / Then la competición se bloqueó antes de
        decidir (el orden de cerrar y reabrir), aunque acabe en INVITATION_ON_HOLD"""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        await _cierra(uow, comp_id, organizador)
        bloqueo = AsyncMock(wraps=uow.competitions.find_by_id_for_update)
        uow.competitions.find_by_id_for_update = bloqueo

        with pytest.raises(InvitationOnHoldViolation):
            await _responde(usuarios, uow, invitacion, invitado, "ACCEPT")

        assert bloqueo.await_count >= 1

    async def test_rechazar_no_bloquea_la_competicion(self):
        """D1. Given una pendiente / When se rechaza / Then no hace falta bloquearla."""
        uow, _, _, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        bloqueo = AsyncMock(wraps=uow.competitions.find_by_id_for_update)
        uow.competitions.find_by_id_for_update = bloqueo

        await _responde(usuarios, uow, invitacion, invitado, "DECLINE")

        assert bloqueo.await_count == 0

    async def test_una_en_espera_impide_otra_al_mismo_correo(self):
        """D1. Given una ON_HOLD (cerrar y reabrir a la vez) en una abierta / When se invita
        otra vez al mismo correo / Then ya hay una: no se duplica"""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id)).put_on_hold()
            await uow.commit()

        with pytest.raises(InvitationOnHoldExistsViolation) as error:
            await SendInvitationByEmailUseCase(uow, usuarios).execute(
                SendInvitationByEmailRequestDTO(
                    competition_id=comp_id.value,
                    inviter_id=organizador.value,
                    invitee_email=str(invitado.email),
                )
            )

        assert error.value.error_code == "INVITATION_ON_HOLD_EXISTS"
        assert str(error.value) == "Esa persona ya tiene una invitación en lista de espera."

    async def test_por_id_tambien(self):
        """D1. Given una ON_HOLD / When se le vuelve a invitar por su cuenta / Then el mismo."""
        uow, comp_id, organizador, _, usuarios, invitado, invitacion = await _abierta_con_invitado()
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id)).put_on_hold()
            await uow.commit()

        with pytest.raises(InvitationOnHoldExistsViolation):
            await SendInvitationByUserIdUseCase(uow, usuarios).execute(
                SendInvitationByUserIdRequestDTO(
                    competition_id=comp_id.value,
                    inviter_id=organizador.value,
                    invitee_user_id=invitado.id.value,
                )
            )

    async def test_no_se_bloquean_las_que_esperan_para_mirar_un_correo(self):
        """D1. Given una ON_HOLD / When se mira si impide otra / Then sin bloquear filas: ya
        está bloqueada la competición"""
        uow, comp_id, _, _, _, invitado, invitacion = await _abierta_con_invitado()
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id)).put_on_hold()
            await uow.commit()
        bloqueo = AsyncMock(wraps=uow.invitations.find_by_competition_and_status_for_update)
        uow.invitations.find_by_competition_and_status_for_update = bloqueo

        async with uow:
            with pytest.raises(InvitationOnHoldExistsViolation):
                await pendiente_vigente(uow, str(invitado.email), comp_id)

        assert bloqueo.await_count == 0

    async def test_una_en_espera_de_otro_correo_no_impide(self):
        """D1. Given una ON_HOLD a otro correo / When se invita / Then se manda."""
        uow, comp_id, organizador, _, usuarios, _, invitacion = await _abierta_con_invitado()
        async with uow:
            (await uow.invitations.find_by_id(invitacion.id)).put_on_hold()
            await uow.commit()

        enviada = await SendInvitationByEmailUseCase(uow, usuarios).execute(
            SendInvitationByEmailRequestDTO(
                competition_id=comp_id.value,
                inviter_id=organizador.value,
                invitee_email=f"otro_{uuid4().hex[:6]}@example.com",
            )
        )

        assert enviada.status == "PENDING"


class TestD2AprobarConLaSalaAbierta:
    async def test_la_ruta_responde_409_con_su_codigo_y_su_texto(self):
        """D2. Given aprobar con la sala abierta / Then 409 DRAFT_IN_PROGRESS, con el texto de
        las rutas de baja"""
        import json

        from src.modules.competition.infrastructure.api.v1.enrollment_routes import (
            approve_enrollment,
        )

        class _Aprobar:
            async def execute(self, *_args, **_kwargs):
                raise DraftInProgressError("Espera a que termine el draft")

        respuesta = await approve_enrollment(
            uuid4(), current_user=MagicMock(id=uuid4(), is_admin=False), use_case=_Aprobar()
        )

        assert respuesta.status_code == 409
        assert json.loads(respuesta.body) == {
            "detail": "Wait until the draft is over.",
            "error_code": "DRAFT_IN_PROGRESS",
        }


class TestO1MoverConLaSalaAbierta:
    async def test_no_se_mueve_nada(self):
        """O1. Given cerrada por el plazo con la sala de draft abierta / When se mueven las
        fechas / Then DRAFT_IN_PROGRESS, con un motivo claro, y las sesiones no se mueven"""
        uow = InMemoryUnitOfWork()
        competition = await r3._cerrada(uow, por_el_plazo=True)
        async with uow:
            await uow.drafts.add(
                Draft(
                    id=DraftId.generate(),
                    competition_id=competition.id,
                    team_a_captain_id=competition.creator_id,
                    team_b_captain_id=UserId(uuid4()),
                    status=DraftStatus.IN_PROGRESS,
                )
            )
            await uow.commit()
        rondas = AsyncMock(wraps=uow.rounds.find_by_competition)
        uow.rounds.find_by_competition = rondas

        with pytest.raises(DraftInProgressError, match="mover las fechas"):
            await UpdateCompetitionUseCase(
                uow, LocationBuilder(uow.countries), r3._Campos(), plazo=r3._plazo(r3.DESPUES)
            ).execute(competition.id, r3._fechas(7), competition.creator_id)

        assert rondas.await_count == 0
        assert competition.dates.start_date == r3.TORNEO


class TestD7LasQueEsperanSeReleen:
    async def test_bloquear_las_de_un_estado_las_relee(self):
        """D7. Given el repositorio SQL / Then bloquearlas las relee (populate_existing):
        si no, la sesión devolvería el objeto de antes del bloqueo (BE #375)"""
        from src.modules.competition.infrastructure.persistence.sqlalchemy.invitation_repository import (
            SQLAlchemyInvitationRepository,
        )

        sentencias = []

        class _Sesion:
            async def execute(self, sentencia):
                sentencias.append(sentencia)
                return MagicMock(scalars=lambda: MagicMock(all=lambda: []))

        await SQLAlchemyInvitationRepository(_Sesion()).find_by_competition_and_status_for_update(
            CompetitionId(uuid4()), InvitationStatus.ON_HOLD
        )

        [sentencia] = sentencias
        assert sentencia.get_execution_options().get("populate_existing") is True
        assert sentencia._for_update_arg is not None


class TestSinTrabajoDeMas:
    async def test_sin_invitaciones_en_espera_no_se_mira_el_sitio(self):
        """C1. Given ninguna ON_HOLD / When se reabre / Then ni se cuentan las plazas."""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        cuenta = AsyncMock(wraps=uow.enrollments.count_approved_by_competition)
        uow.enrollments.count_approved_by_competition = cuenta

        await _reabre(uow, comp_id, organizador)

        assert cuenta.await_count == 0

    async def test_sin_nadie_sin_cuenta_no_se_leen_usuarios(self):
        """O2. Given solo invitados con cuenta / When se reabre / Then no se buscan nombres."""
        uow, comp_id, organizador, _ = await _cerrada_ryder()
        _, invitado = await _usuarios()
        await _en_espera(uow, comp_id, invitado)
        usuarios = UsuariosEnMemoria()
        busca = AsyncMock(wraps=usuarios.users.find_by_ids)
        usuarios.users.find_by_ids = busca

        await ReopenEnrollmentsUseCase(uow, correos=_Correos(), user_uow=usuarios).execute(
            ReopenEnrollmentsRequestDTO(competition_id=comp_id.value), organizador
        )

        assert busca.await_count == 0


class TestAlLlenarseApuntandose:
    async def test_quien_llena_una_publica_cierra_las_pendientes_y_retira_su_aviso(self):
        """BE #359 con el aviso: Given una pública con una plaza y una invitación pendiente
        / When alguien se apunta y la llena / Then la invitación, NO_ROOM y fuera su aviso"""
        uow, comp_id, _, _, _, _, invitacion = await _abierta_con_invitado()
        async with uow:
            competicion = await uow.competitions.find_by_id(comp_id)
            # Pública y por jugar: si no, la fecha la rechaza antes
            empieza = datetime.now().date() + timedelta(days=30)
            competicion.update_info(
                visibility=Visibility.PUBLIC,
                dates=DateRange(empieza, empieza + timedelta(days=2)),
            )
            competicion._max_players = 3  # el organizador y otro: queda una
            await uow.competitions.update(competicion)
            await uow.commit()
        actividad = _Actividad()

        await RequestEnrollmentUseCase(uow, USUARIOS_CON_GENERO, actividad=actividad).execute(
            RequestEnrollmentRequestDTO(competition_id=comp_id.value, user_id=uuid4())
        )

        assert await _estado(uow, invitacion) is InvitationStatus.NO_ROOM
        [(cerradas,)] = actividad.de("invitations_closed")
        assert [i.id for i in cerradas] == [invitacion.id]
