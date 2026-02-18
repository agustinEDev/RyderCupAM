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
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.events.invitation_accepted_event import (
    InvitationAcceptedEvent,
)
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
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

    async def execute(
        self, request: RespondInvitationRequestDTO
    ) -> RespondInvitationResponseDTO:
        invitation_id = InvitationId(request.invitation_id)
        current_user_id = UserId(request.user_id)
        action = request.action.upper()

        if action not in ("ACCEPT", "DECLINE"):
            raise ValueError(f"Invalid action: {action}. Must be ACCEPT or DECLINE.")

        # Obtener email del usuario actual
        async with self._user_uow:
            current_user = await self._user_uow.users.find_by_id(current_user_id)
            current_user_email = str(current_user.email) if current_user else None

        enrollment_id = None

        async with self._uow:
            # 1. Buscar y validar invitation
            invitation = await self._uow.invitations.find_by_id(invitation_id)
            if not invitation:
                raise InvitationNotFoundError(
                    f"Invitation not found: {request.invitation_id}"
                )

            invitation.check_expiration()

            if not invitation.is_pending():
                raise InvalidInvitationStatusViolation(
                    f"Invitation is in status {invitation.status.value}. "
                    "Only PENDING invitations can be responded to."
                )

            # 2. Verificar current_user es invitee
            is_invitee = invitation.is_for_user(current_user_id) or (
                current_user_email and invitation.is_for_email(current_user_email)
            )
            if not is_invitee:
                raise NotInviteeError("You are not the invitee of this invitation.")

            # 3. Ejecutar accion
            if action == "ACCEPT":
                enrollment_id = await self._handle_accept(invitation, current_user_id)
            else:
                await self._handle_decline(invitation)

        # 4. Construir respuesta enriquecida
        return await self._build_response(invitation, enrollment_id)

    async def _handle_accept(self, invitation, current_user_id: UserId):
        """Procesa la aceptacion de una invitacion."""
        competition = await self._uow.competitions.find_by_id(invitation.competition_id)
        if not competition:
            raise CompetitionNotFoundError(
                f"Competition not found: {invitation.competition_id}"
            )

        CompetitionPolicy.can_accept_invitation(competition.status)

        existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
            current_user_id, invitation.competition_id
        )
        if existing_enrollment and existing_enrollment.is_approved():
            raise InvalidInvitationStatusViolation(
                "User is already enrolled in this competition."
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

        event = InvitationAcceptedEvent(
            invitation_id=str(invitation.id),
            competition_id=str(invitation.competition_id),
            invitee_user_id=str(current_user_id),
            enrollment_id=str(enrollment.id.value),
        )
        invitation._add_domain_event(event)

        await self._uow.enrollments.add(enrollment)
        await self._uow.invitations.update(invitation)

        return enrollment.id.value

    async def _handle_decline(self, invitation):
        """Procesa el rechazo de una invitacion."""
        invitation.decline()
        await self._uow.invitations.update(invitation)

    async def _build_response(self, invitation, enrollment_id) -> RespondInvitationResponseDTO:
        """Construye el DTO de respuesta enriquecido con nombres."""
        async with self._user_uow:
            inviter_user = await self._user_uow.users.find_by_id(invitation.inviter_id)
            inviter_name = (
                f"{inviter_user.first_name} {inviter_user.last_name}"
                if inviter_user
                else "Unknown"
            )

            invitee_name = None
            if invitation.invitee_user_id:
                invitee_user = await self._user_uow.users.find_by_id(
                    invitation.invitee_user_id
                )
                if invitee_user:
                    invitee_name = f"{invitee_user.first_name} {invitee_user.last_name}"

        async with self._uow:
            competition = await self._uow.competitions.find_by_id(
                invitation.competition_id
            )
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
