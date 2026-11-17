"""Caso de Uso: Enviar Invitacion por User ID."""

import logging

from src.modules.competition.application.dto.invitation_dto import (
    InvitationResponseDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.exceptions import InviteeNotFoundError
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.envio_de_invitaciones import (
    Destinatario,
    EnvioDeInvitaciones,
    Peticion,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.exceptions.competition_violations import (
    AlreadyEnrolledInvitationViolation,
    SelfInvitationViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class SendInvitationByUserIdUseCase:
    """Envia una invitacion a un usuario registrado por su user_id."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        email_service: IInvitationEmailService | None = None,
        actividad: CompetitionActivityPublisherInterface | None = None,
        plazo: PlazoDeInscripcion | None = None,
    ):
        self._uow = uow
        self._user_uow = user_uow
        # Los avisos de Actividad (BE-2); sin el, no se avisa
        self._actividad = AvisosDeActividad(actividad)
        # Lo común con invitar por correo (re-auditoría F-09)
        self._envio = EnvioDeInvitaciones(
            uow, user_uow, email_service, self._actividad, plazo, logger
        )

    async def execute(
        self, request: SendInvitationByUserIdRequestDTO, is_admin: bool = False
    ) -> InvitationResponseDTO:
        """
        Invita a un usuario por su id a la competición.

        Args:
            request: A quién, a qué competición y con qué mensaje
            is_admin: Si quien invita es administrador (no hace falta organizar)

        Returns:
            La invitación creada, con los nombres

        Raises:
            Las del organizador, el estado, el cupo, el freno por hora y la
            pendiente duplicada (una pendiente ya caducada no cuenta)
        """
        inviter_id = UserId(request.inviter_id)
        invitee_user_id = UserId(request.invitee_user_id)

        async def destinatario_de(competition: Competition) -> Destinatario:
            # 4. Buscar invitee user
            async with self._user_uow:
                invitee_user = await self._user_uow.users.find_by_id(invitee_user_id)
                if not invitee_user:
                    raise InviteeNotFoundError(f"User not found: {request.invitee_user_id}")
                invitee_email = str(invitee_user.email)
                invitee_name = invitee_user.display_name

            # 5. No self-invitation
            if inviter_id == invitee_user_id:
                raise SelfInvitationViolation("Cannot invite yourself to a competition.")

            # 6. Verificar no enrollment activo
            existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
                invitee_user_id, competition.id
            )
            if existing_enrollment and existing_enrollment.is_approved():
                raise AlreadyEnrolledInvitationViolation(
                    f"User {request.invitee_user_id} is already enrolled in competition "
                    f"{request.competition_id}."
                )
            # Al organizador, el nombre de quien eligió, nunca su correo (B-01); el
            # correo de la invitación va a su cuenta tal cual está
            return Destinatario(
                correo=invitee_email,
                correo_de_la_pendiente=invitee_email,
                user_id=invitee_user_id,
                nombre=invitee_name,
                por_correo=False,
                correo_del_aviso=invitee_email,
            )

        return await self._envio.enviar(
            Peticion(
                competition_ref=request.competition_id,
                inviter_id=inviter_id,
                personal_message=request.personal_message,
                is_admin=is_admin,
            ),
            destinatario_de,
        )
