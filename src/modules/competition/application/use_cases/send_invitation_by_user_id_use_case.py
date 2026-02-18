"""Caso de Uso: Enviar Invitacion por User ID."""

from datetime import datetime, timedelta

from src.modules.competition.application.dto.invitation_dto import (
    InvitationResponseDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    InviteeNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    AlreadyEnrolledInvitationViolation,
    DuplicateInvitationViolation,
    InvitationCompetitionStatusViolation,
    InvitationRateLimitViolation,
    SelfInvitationViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SendInvitationByUserIdUseCase:
    """Envia una invitacion a un usuario registrado por su user_id."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(
        self, request: SendInvitationByUserIdRequestDTO
    ) -> InvitationResponseDTO:
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            inviter_id = UserId(request.inviter_id)
            invitee_user_id = UserId(request.invitee_user_id)

            # 1. Buscar competition
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competition not found: {request.competition_id}"
                )

            # 2. Verificar creator/admin
            if not competition.is_creator(inviter_id):
                raise NotCompetitionCreatorError(
                    "Only the competition creator can send invitations."
                )

            # 3. Validar estado de competicion
            try:
                CompetitionPolicy.can_send_invitation(competition.status)
            except InvitationCompetitionStatusViolation:
                raise

            # 3b. Validar rate limit (max_players invitaciones por hora)
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_invitations = await self._uow.invitations.count_by_competition(
                competition_id, since=one_hour_ago
            )
            try:
                CompetitionPolicy.validate_invitation_rate(
                    recent_invitations, competition.max_players, competition_id
                )
            except InvitationRateLimitViolation:
                raise

            # 4. Buscar invitee user
            async with self._user_uow:
                invitee_user = await self._user_uow.users.find_by_id(invitee_user_id)
                if not invitee_user:
                    raise InviteeNotFoundError(
                        f"User not found: {request.invitee_user_id}"
                    )
                invitee_email = str(invitee_user.email)
                invitee_name = f"{invitee_user.first_name} {invitee_user.last_name}"

            # 5. No self-invitation
            if inviter_id == invitee_user_id:
                raise SelfInvitationViolation("Cannot invite yourself to a competition.")

            # 6. Verificar no enrollment activo
            existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
                invitee_user_id, competition_id
            )
            if existing_enrollment and existing_enrollment.is_approved():
                raise AlreadyEnrolledInvitationViolation(
                    f"User {request.invitee_user_id} is already enrolled in competition "
                    f"{request.competition_id}."
                )

            # 7. Verificar no invitation PENDING duplicada
            existing_invitation = (
                await self._uow.invitations.find_pending_by_email_and_competition(
                    invitee_email, competition_id
                )
            )
            if existing_invitation:
                raise DuplicateInvitationViolation(
                    f"A pending invitation already exists for {invitee_email} "
                    f"in competition {request.competition_id}."
                )

            # 8. Crear invitation
            invitation = Invitation.create(
                id=InvitationId.generate(),
                competition_id=competition_id,
                inviter_id=inviter_id,
                invitee_email=invitee_email,
                invitee_user_id=invitee_user_id,
                personal_message=request.personal_message,
            )

            # 9. Persistir
            await self._uow.invitations.add(invitation)

        # 10. Retornar DTO enriquecido
        # Obtener inviter_name
        async with self._user_uow:
            inviter_user = await self._user_uow.users.find_by_id(inviter_id)
            inviter_name = (
                f"{inviter_user.first_name} {inviter_user.last_name}"
                if inviter_user
                else "Unknown"
            )

        return InvitationResponseDTO(
            id=invitation.id.value,
            competition_id=invitation.competition_id.value,
            competition_name=str(competition.name),
            inviter_id=invitation.inviter_id.value,
            inviter_name=inviter_name,
            invitee_email=invitation.invitee_email,
            invitee_user_id=invitation.invitee_user_id.value if invitation.invitee_user_id else None,
            invitee_name=invitee_name,
            status=invitation.status.value,
            personal_message=invitation.personal_message,
            expires_at=invitation.expires_at,
            responded_at=invitation.responded_at,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
        )
