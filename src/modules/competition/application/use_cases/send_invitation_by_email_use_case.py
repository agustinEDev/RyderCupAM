"""Caso de Uso: Enviar Invitacion por Email."""

import logging
from datetime import datetime, timedelta

from src.modules.competition.application.dto.invitation_dto import (
    InvitationResponseDTO,
    SendInvitationByEmailRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    AlreadyEnrolledInvitationViolation,
    DuplicateInvitationViolation,
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
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


def _mask_email(email: str) -> str:
    """Enmascara un email para logging seguro (ej: t***@example.com)."""
    parts = email.split("@")
    if len(parts) != 2 or not parts[0]:
        return "***"
    local = parts[0]
    masked_local = local[0] + "***" if len(local) > 1 else "***"
    return f"{masked_local}@{parts[1]}"


class SendInvitationByEmailUseCase:
    """Envia una invitacion a un email (usuario registrado o no)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        email_service: IInvitationEmailService | None = None,
    ):
        self._uow = uow
        self._user_uow = user_uow
        self._email_service = email_service

    async def execute(
        self, request: SendInvitationByEmailRequestDTO
    ) -> InvitationResponseDTO:
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            inviter_id = UserId(request.inviter_id)

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
            CompetitionPolicy.can_send_invitation(competition.status)

            # 3b. Validar rate limit (max_players invitaciones por hora)
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_invitations = await self._uow.invitations.count_by_competition(
                competition_id, since=one_hour_ago
            )
            CompetitionPolicy.validate_invitation_rate(
                recent_invitations, competition.max_players, competition_id
            )

            # 4. Buscar user por email (puede no existir)
            invitee_user_id = None
            invitee_name = None
            async with self._user_uow:
                try:
                    email_vo = Email(request.invitee_email)
                    invitee_user = await self._user_uow.users.find_by_email(email_vo)
                except ValueError:
                    invitee_user = None

                if invitee_user:
                    invitee_user_id = invitee_user.id
                    invitee_name = f"{invitee_user.first_name} {invitee_user.last_name}"

                    # 5a. No self-invitation
                    if inviter_id == invitee_user_id:
                        raise SelfInvitationViolation(
                            "Cannot invite yourself to a competition."
                        )

            # 5b. Verificar no enrollment activo (ya dentro del UoW de competition)
            if invitee_user_id:
                existing_enrollment = (
                    await self._uow.enrollments.find_by_user_and_competition(
                        invitee_user_id, competition_id
                    )
                )
                if existing_enrollment and existing_enrollment.is_approved():
                    raise AlreadyEnrolledInvitationViolation(
                        f"User with email {request.invitee_email} is already "
                        f"enrolled in competition {request.competition_id}."
                    )

            # 6. Verificar no invitation PENDING duplicada
            existing_invitation = (
                await self._uow.invitations.find_pending_by_email_and_competition(
                    request.invitee_email.strip().lower(), competition_id
                )
            )
            if existing_invitation:
                raise DuplicateInvitationViolation(
                    f"A pending invitation already exists for {request.invitee_email} "
                    f"in competition {request.competition_id}."
                )

            # 7. Crear invitation
            invitation = Invitation.create(
                id=InvitationId.generate(),
                competition_id=competition_id,
                inviter_id=inviter_id,
                invitee_email=request.invitee_email,
                invitee_user_id=invitee_user_id,
                personal_message=request.personal_message,
            )

            # 8. Persistir
            await self._uow.invitations.add(invitation)

        # 9. Retornar DTO enriquecido
        async with self._user_uow:
            inviter_user = await self._user_uow.users.find_by_id(inviter_id)
            inviter_name = (
                f"{inviter_user.first_name} {inviter_user.last_name}"
                if inviter_user
                else "Unknown"
            )

        # 10. Enviar email de invitacion (fuera de la transaccion, no bloquea la creacion)
        if self._email_service:
            try:
                await self._email_service.send_invitation_email(
                    to_email=invitation.invitee_email,
                    invitee_name=invitee_name,
                    inviter_name=inviter_name,
                    competition_name=str(competition.name),
                    personal_message=invitation.personal_message,
                    expires_at=invitation.expires_at,
                )
            except Exception as e:
                logger.warning(
                    "Failed to send invitation email to %s: %s",
                    _mask_email(invitation.invitee_email),
                    str(e),
                )

        return InvitationResponseDTO(
            id=invitation.id.value,
            competition_id=invitation.competition_id.value,
            competition_name=str(competition.name),
            inviter_id=invitation.inviter_id.value,
            inviter_name=inviter_name,
            invitee_email=invitation.invitee_email,
            invitee_user_id=invitee_user_id.value if invitee_user_id else None,
            invitee_name=invitee_name,
            status=invitation.status.value,
            personal_message=invitation.personal_message,
            expires_at=invitation.expires_at,
            responded_at=invitation.responded_at,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
        )
