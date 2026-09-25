"""Caso de Uso: Responder a una Invitacion (ACCEPT/DECLINE)."""

from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
    RespondInvitationResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    InvitationNotFoundError,
    NotInviteeError,
)
from src.modules.competition.application.services.genero_obligatorio import exigir_genero
from src.modules.competition.application.services.nombre_de_quien_invita import (
    nombre_de_quien_invita,
    quieren_su_nombre_legal,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
    InvitationNoRoomViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import (
    INSCRIPCION_CERRADA,
    CompetitionPolicy,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class RespondToInvitationUseCase:
    """Permite al invitado aceptar o rechazar una invitacion."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(self, request: RespondInvitationRequestDTO) -> RespondInvitationResponseDTO:
        invitation_id = InvitationId(request.invitation_id)
        current_user_id = UserId(request.user_id)
        action = request.action.upper()

        if action not in ("ACCEPT", "DECLINE"):
            raise ValueError(f"Invalid action: {action}. Must be ACCEPT or DECLINE.")

        # Obtener email del usuario actual
        async with self._user_uow:
            current_user = await self._user_uow.users.find_by_id(current_user_id)
            if not current_user:
                raise NotInviteeError("Authenticated user not found. Cannot respond to invitation.")
            current_user_email = str(current_user.email)

        # Fase 1: Verificar expiracion y persistir si cambio
        non_pending_status = None
        sin_plaza = False
        async with self._uow:
            invitation = await self._uow.invitations.find_by_id(invitation_id)
            if not invitation:
                raise InvitationNotFoundError(f"Invitation not found: {request.invitation_id}")

            invitation.check_expiration()

            if not invitation.is_pending():
                # Persistir el cambio de estado (ej: PENDING -> EXPIRED)
                await self._uow.invitations.update(invitation)
                non_pending_status = invitation.status.value
            elif (
                action == "ACCEPT"
                # Solo el invitado: con el id de otra no se le cambia nada
                and self._es_el_invitado(invitation, current_user_id, current_user_email)
                and await self._inscripcion_cerrada(invitation)
            ):
                # Una pendiente de antes de que el cierre las rechazara (#710):
                # se queda sin plaza, guardado, y no se entra
                invitation.reject_for_no_room()
                await self._uow.invitations.update(invitation)
                sin_plaza = True

        if sin_plaza:
            raise InvitationNoRoomViolation()
        # Una ya sin plaza lo dice en su idioma, no con el estado en crudo
        if non_pending_status == InvitationStatus.NO_ROOM.value:
            raise InvitationNoRoomViolation()
        # Si la invitacion no estaba pending, el commit ya ocurrio; ahora lanzamos
        if non_pending_status:
            raise InvalidInvitationStatusViolation(
                f"Invitation is in status {non_pending_status}. "
                "Only PENDING invitations can be responded to."
            )

        # Fase 2: Procesar la respuesta
        enrollment_id = None
        competition_name = None

        async with self._uow:
            # Re-fetch para tener la entidad en la sesion actual
            invitation = await self._releer_pendiente(invitation_id)

            # Verificar current_user es invitee
            if not self._es_el_invitado(invitation, current_user_id, current_user_email):
                raise NotInviteeError("You are not the invitee of this invitation.")

            # Ejecutar accion
            if action == "ACCEPT":
                enrollment_id, competition_name = await self._handle_accept(
                    invitation, current_user_id
                )
            else:
                await self._handle_decline(invitation)

        # Construir respuesta enriquecida
        return await self._build_response(invitation, enrollment_id, competition_name)

    async def _releer_pendiente(self, invitation_id: InvitationId) -> Invitation:
        """La invitacion de la fase 2, que tiene que seguir pendiente.

        El cierre pudo llegar entre las dos fases y dejarla sin plaza: se dice
        con su codigo, no con el generico (revision local de la BE #385).
        """
        invitation = await self._uow.invitations.find_by_id(invitation_id)
        if invitation and invitation.status == InvitationStatus.NO_ROOM:
            raise InvitationNoRoomViolation()
        if not invitation or not invitation.is_pending():
            raise InvalidInvitationStatusViolation("Invitation is no longer pending.")
        return invitation

    @staticmethod
    def _es_el_invitado(invitation, user_id: UserId, email: str) -> bool:
        """Si quien responde es el invitado, por su cuenta o por su email."""
        return invitation.is_for_user(user_id) or invitation.is_for_email(email)

    async def _inscripcion_cerrada(self, invitation) -> bool:
        """Si su competicion ya cerro la inscripcion: no quedan plazas."""
        competition = await self._uow.competitions.find_by_id(invitation.competition_id)
        return competition is not None and competition.status in INSCRIPCION_CERRADA

    async def _handle_accept(self, invitation, current_user_id: UserId):
        """Procesa la aceptacion de una invitacion. Retorna (enrollment_id, competition_name)."""
        # Con la fila bloqueada: si se cierra a la vez, uno espera al otro y aquí
        # se lee el estado de verdad, no un «abierta» de antes del cierre (#710)
        competition = await self._uow.competitions.find_by_id_for_update(invitation.competition_id)
        if not competition:
            raise CompetitionNotFoundError(f"Competition not found: {invitation.competition_id}")

        CompetitionPolicy.can_accept_invitation(competition.status)

        # Sin género no se sabe desde qué barras juega (#710). Antes de aceptar:
        # la invitación se queda pendiente para cuando lo rellene
        await exigir_genero(self._user_uow.users, current_user_id, es_quien_se_apunta=True)

        existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
            current_user_id, invitation.competition_id
        )
        if existing_enrollment:
            raise InvalidInvitationStatusViolation(
                "User already has an enrollment in this competition."
            )

        approved_count = await self._uow.enrollments.count_approved_by_competition(
            invitation.competition_id
        )
        CompetitionPolicy.validate_capacity(
            approved_count, competition.max_players, invitation.competition_id
        )

        invitation.accept()

        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(invitation.competition_id.value),
            user_id=current_user_id,
        )

        await self._uow.enrollments.add(enrollment)
        await self._uow.invitations.update(invitation)

        return enrollment.id.value, str(competition.name)

    async def _handle_decline(self, invitation):
        """Procesa el rechazo de una invitacion."""
        invitation.decline()
        await self._uow.invitations.update(invitation)

    async def _build_response(
        self, invitation, enrollment_id, competition_name=None
    ) -> RespondInvitationResponseDTO:
        """Construye el DTO de respuesta enriquecido con nombres."""
        # El mismo nombre que la lista sobre la que se pinta: con uno distinto,
        # aceptar una invitación cambiaba el nombre en la pantalla (BE #239,
        # #710). El que usa quien invita en ESA competición
        async with self._uow:
            legal = bool(
                await quieren_su_nombre_legal(
                    self._uow, [(invitation.competition_id, invitation.inviter_id)]
                )
            )
        async with self._user_uow:
            inviter_user = await self._user_uow.users.find_by_id(invitation.inviter_id)
            inviter_name = nombre_de_quien_invita(inviter_user, legal)

            invitee_name = None
            if invitation.invitee_user_id:
                invitee_user = await self._user_uow.users.find_by_id(invitation.invitee_user_id)
                if invitee_user:
                    invitee_name = invitee_user.display_name

        # Solo buscar competition si no fue pasado (path DECLINE)
        if not competition_name:
            async with self._uow:
                competition = await self._uow.competitions.find_by_id(invitation.competition_id)
                competition_name = str(competition.name) if competition else "Unknown"

        return RespondInvitationResponseDTO(
            id=invitation.id.value,
            competition_id=invitation.competition_id.value,
            competition_name=competition_name,
            inviter_id=invitation.inviter_id.value,
            inviter_name=inviter_name,
            invitee_email=invitation.invitee_email,
            invitee_user_id=(
                invitation.invitee_user_id.value if invitation.invitee_user_id else None
            ),
            invitee_name=invitee_name,
            status=invitation.status.value,
            personal_message=invitation.personal_message,
            expires_at=invitation.expires_at,
            responded_at=invitation.responded_at,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
            enrollment_id=enrollment_id,
        )
