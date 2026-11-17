"""Caso de Uso: Enviar Invitacion por Email."""

import logging

from src.modules.competition.application.dto.invitation_dto import (
    InvitationResponseDTO,
    SendInvitationByEmailRequestDTO,
)
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
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class SendInvitationByEmailUseCase:
    """Envia una invitacion a un email (usuario registrado o no)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        email_service: IInvitationEmailService | None = None,
        actividad: CompetitionActivityPublisherInterface | None = None,
        plazo: PlazoDeInscripcion | None = None,
    ):
        self._uow = uow
        # Pasado el plazo de inscripción no se invita (C2, 15 nov 2026); sin él, no se mira
        self._plazo = plazo
        self._user_uow = user_uow
        # Los avisos de Actividad (BE-2); sin el, no se avisa
        self._actividad = AvisosDeActividad(actividad)
        # Lo común con invitar por id (re-auditoría F-09)
        self._envio = EnvioDeInvitaciones(
            uow, user_uow, email_service, self._actividad, plazo, logger
        )

    async def _cuenta_del_correo(self, invitee_email: str, inviter_id: UserId) -> User | None:
        """La cuenta de ese correo, verificada o no, o None; nunca la de quien invita."""
        async with self._user_uow:
            try:
                invitee_user = await self._user_uow.users.find_by_email(Email(invitee_email))
            except ValueError:
                invitee_user = None
        # 5a. No self-invitation
        if invitee_user and inviter_id == invitee_user.id:
            raise SelfInvitationViolation("Cannot invite yourself to a competition.")
        return invitee_user

    async def execute(
        self, request: SendInvitationByEmailRequestDTO, is_admin: bool = False
    ) -> InvitationResponseDTO:
        """
        Invita a un correo (con cuenta o sin ella) a la competición.

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

        async def destinatario_de(competition: Competition) -> Destinatario:
            # 4 y 5a. Buscar user por email (puede no existir); no a uno mismo
            invitee_user = await self._cuenta_del_correo(request.invitee_email, inviter_id)
            # Solo se ata a una cuenta que ha verificado ese correo (F-07, fase 3): sin
            # verificar, queda «enviada a un correo», sin su nombre ni aviso en
            # Actividad, y la verá al verificar por el casado por correo
            atada = invitee_user if invitee_user and invitee_user.email_verified else None

            # 5b. Verificar no enrollment activo (ya dentro del UoW de competition):
            # con cuenta, verificada o no. Se dice claro: el organizador ya ve los correos
            # de sus inscritos (BE #531), así que no revela nada (decidido por Agustín el
            # 14 nov 2026, tras probar una respuesta igual que se distinguía)
            if invitee_user:
                existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
                    invitee_user.id, competition.id
                )
                if existing_enrollment and existing_enrollment.is_approved():
                    raise AlreadyEnrolledInvitationViolation(
                        f"User is already enrolled in competition {request.competition_id}."
                    )
            return Destinatario(
                correo=request.invitee_email,
                correo_de_la_pendiente=request.invitee_email.strip().lower(),
                user_id=atada.id if atada else None,
                nombre=atada.display_name if atada else None,
                por_correo=True,
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
