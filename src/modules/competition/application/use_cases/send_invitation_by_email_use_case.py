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
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.cupo_de_la_competicion import (
    exigir_sitio,
)
from src.modules.competition.application.services.equipos_formados import (
    exigir_sin_equipos_formados,
)
from src.modules.competition.application.services.invitacion_que_impide import pendiente_vigente
from src.modules.competition.application.services.lo_que_ve_el_organizador import (
    lo_que_ve_el_organizador,
)
from src.modules.competition.application.services.nombre_de_quien_invita import (
    nombre_de_quien_invita,
    quieren_su_nombre_legal,
)
from src.modules.competition.domain.entities.competition import Competition
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
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.email_masking import mask_email as _mask_email

logger = logging.getLogger(__name__)


class SendInvitationByEmailUseCase:
    """Envia una invitacion a un email (usuario registrado o no)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        email_service: IInvitationEmailService | None = None,
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        self._uow = uow
        self._user_uow = user_uow
        self._email_service = email_service
        # Los avisos de Actividad (BE-2); sin el, no se avisa
        self._actividad = AvisosDeActividad(actividad)

    async def _avisar(
        self, competition: Competition, invitation: Invitation, caducada: Invitation | None
    ) -> None:
        """
        Ya guardada: si tiene cuenta, le sale en Actividad (BE-2); y la que
        caducó sin abrirse y dio paso a esta pierde su aviso (CodeRabbit).
        """
        await self._actividad.invited(competition, invitation)
        if caducada is not None:
            await self._actividad.invitations_closed([caducada])

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
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            inviter_id = UserId(request.inviter_id)

            # 1. Buscar competition
            # Con la fila bloqueada (BE #359): una inscripcion que llena la ultima
            # plaza entre comprobar el cupo y guardar dejaba una pendiente nueva en
            # un torneo lleno. Mismo orden que las inscripciones
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if not competition:
                raise CompetitionNotFoundError(f"Competition not found: {request.competition_id}")

            # 2. Verificar creator/admin
            if not is_admin and not competition.is_creator(inviter_id):
                raise NotCompetitionCreatorError(
                    "Only the competition creator can send invitations."
                )

            # 3. Validar estado de competicion
            CompetitionPolicy.can_send_invitation(competition.status)
            # Con los equipos formados no podría aceptarse (30 oct 2026)
            await exigir_sin_equipos_formados(self._uow, competition.id)

            # 4 y 5a. Buscar user por email (puede no existir); no a uno mismo
            invitee_user = await self._cuenta_del_correo(request.invitee_email, inviter_id)
            # Solo se ata a una cuenta que ha verificado ese correo (F-07, fase 3): sin
            # verificar, queda «enviada a un correo», sin su nombre ni aviso en
            # Actividad, y la verá al verificar por el casado por correo
            atada = invitee_user if invitee_user and invitee_user.email_verified else None
            invitee_user_id = atada.id if atada else None
            invitee_name = atada.display_name if atada else None

            # 5b. Verificar no enrollment activo (ya dentro del UoW de competition):
            # con cuenta, verificada o no. Se dice claro: el organizador ya ve los correos
            # de sus inscritos (BE #531), así que no revela nada (decidido por Agustín el
            # 14 nov 2026, tras probar una respuesta igual que se distinguía)
            if invitee_user:
                existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
                    invitee_user.id, competition_id
                )
                if existing_enrollment and existing_enrollment.is_approved():
                    raise AlreadyEnrolledInvitationViolation(
                        f"User is already enrolled in competition {request.competition_id}."
                    )

            # Solo mientras queden plazas (BE #359): libres = max_players menos
            # aprobadas. Antes se invitaba a un torneo lleno y quien llegaba tarde
            # se enteraba al aceptar, sin haber hecho nada mal. Las pendientes no
            # ocupan plaza: cuando una acepta y llena la ultima, las demas se quedan
            # sin plaza (ver RespondToInvitationUseCase)
            # Con franjas, el cupo es de sus plazas: aquí no se mira (28 oct 2026)
            await exigir_sitio(self._uow, competition)

            # Rate limit (min(max_players, MAX_INVITATIONS_PER_HOUR) por hora), despues
            # de las plazas: una competicion llena con el freno agotado decia
            # «espera» cuando lo cierto es que ya no cabe nadie
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_invitations = await self._uow.invitations.count_by_competition(
                competition_id, since=one_hour_ago
            )
            CompetitionPolicy.validate_invitation_rate(
                recent_invitations, competition.max_players, competition_id
            )

            # Y el de quien invita, sumando todas sus competiciones (auditoría de la
            # fase 6, B-03)
            del_organizador = await self._uow.invitations.count_by_inviter(
                inviter_id, since=one_hour_ago
            )
            CompetitionPolicy.validate_user_invitation_rate(del_organizador)

            # 6. Verificar no invitation PENDING duplicada
            # Una pendiente que ya caducó sin que nadie la abriera no impide
            # invitar otra vez (release social 2)
            existing_invitation, caducada = await pendiente_vigente(
                self._uow, request.invitee_email.strip().lower(), competition_id
            )
            if existing_invitation:
                raise DuplicateInvitationViolation(
                    # Sin el correo: el mensaje sale en la respuesta (revisor de B-01)
                    f"A pending invitation already exists in competition {request.competition_id}."
                )

            # 7. Crear invitation
            invitation = Invitation.create(
                id=InvitationId.generate(),
                competition_id=competition_id,
                inviter_id=inviter_id,
                invitee_email=request.invitee_email,
                invitee_user_id=invitee_user_id,
                personal_message=request.personal_message,
                sent_by_email=True,
            )

            # 8. Persistir
            await self._uow.invitations.add(invitation)

            # 10. Y con la primera invitacion se abren las inscripciones (BE #319).
            # Aqui y no antes: abrir y fallar luego dejaria el torneo abierto sin
            # nadie invitado, que es medio arranque
            if CompetitionPolicy.invitation_opens_enrollment(competition.status):
                competition.activate()
                await self._uow.competitions.update(competition)

            # El nombre que usa en ESTA competición (#710), también en el correo
            legal = bool(await quieren_su_nombre_legal(self._uow, [(competition_id, inviter_id)]))

        # Ya guardada: si tiene cuenta, le sale en Actividad (BE-2)
        await self._avisar(competition, invitation, caducada)

        # 9. Retornar DTO enriquecido
        async with self._user_uow:
            # Como aparece en la competicion, tambien en el correo: ver el
            # comentario gemelo en send_invitation_by_user_id_use_case
            inviter_user = await self._user_uow.users.find_by_id(inviter_id)
            inviter_name = nombre_de_quien_invita(inviter_user, legal)

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

        return self._respuesta(invitation, competition, inviter_name, invitee_name)

    @staticmethod
    def _respuesta(
        invitation: Invitation,
        competition: Competition,
        inviter_name: str,
        invitee_name: str | None,
    ) -> InvitationResponseDTO:
        """Al organizador, solo el correo que tecleó mientras no responda (B-03)."""
        quien = lo_que_ve_el_organizador(invitation, invitee_name)
        return InvitationResponseDTO(
            id=invitation.id.value,
            competition_id=invitation.competition_id.value,
            competition_name=str(competition.name),
            inviter_id=invitation.inviter_id.value,
            inviter_name=inviter_name,
            invitee_email=quien.email,
            invitee_user_id=quien.user_id.value if quien.user_id else None,
            invitee_name=quien.nombre,
            status=invitation.status.value,
            personal_message=invitation.personal_message,
            expires_at=invitation.expires_at,
            responded_at=invitation.responded_at,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
        )
