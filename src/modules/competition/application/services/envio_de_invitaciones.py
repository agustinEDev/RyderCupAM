"""
EnvioDeInvitaciones - Lo común de invitar por correo y por id (re-auditoría F-09).

Los dos casos de uso hacían lo mismo salvo decidir a quién va la invitación: el
de correo busca la cuenta de ese correo (puede no tenerla), el de id la exige.
Aquí está el resto, en el mismo orden: el organizador y el estado de la
competición, el plazo, el cupo, los dos frenos por hora, la pendiente
duplicada, guardar, abrir las inscripciones con la primera, los avisos, el
correo y la respuesta.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from src.modules.competition.application.dto.invitation_dto import InvitationResponseDTO
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.cupo_de_la_competicion import exigir_sitio
from src.modules.competition.application.services.enrollment_opener import EnrollmentOpener
from src.modules.competition.application.services.equipos_formados import (
    exigir_que_se_pueda_invitar,
)
from src.modules.competition.application.services.invitacion_que_impide import pendiente_vigente
from src.modules.competition.application.services.lo_que_ve_el_organizador import (
    lo_que_ve_el_organizador,
)
from src.modules.competition.application.services.nombre_de_quien_invita import (
    nombre_de_quien_invita,
    quieren_su_nombre_legal,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
    exigir_el_plazo,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    DuplicateInvitationViolation,
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
from src.shared.domain.services.email_masking import mask_email as _mask_email
from src.shared.domain.services.instante_utc import ahora_utc_sin_zona


@dataclass(frozen=True)
class Destinatario:
    """A quién va la invitación, tal como lo resuelve cada caso de uso."""

    # El correo que se guarda en la invitación
    correo: str
    # Con el que se busca una pendiente vigente para esa competición
    correo_de_la_pendiente: str
    # La cuenta a la que se ata, si se ata a alguna
    user_id: UserId | None
    # Su nombre, para el correo y para la respuesta
    nombre: str | None
    # Si se envió a un correo tecleado por el organizador
    por_correo: bool
    # A dónde va el correo de la invitación; None: al que guarda la invitación
    correo_del_aviso: str | None = None


@dataclass(frozen=True)
class Peticion:
    """Lo común de las dos peticiones."""

    # Tal como llegó: es lo que nombran los mensajes de error
    competition_ref: UUID | str
    inviter_id: UserId
    personal_message: str | None
    is_admin: bool


ResolverDestinatario = Callable[[Competition], Awaitable[Destinatario]]


class EnvioDeInvitaciones:
    """Invita a la competición a quien resuelva cada caso de uso."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        email_service: IInvitationEmailService | None,
        actividad: AvisosDeActividad,
        plazo: PlazoDeInscripcion | None,
        logger: logging.Logger,
    ):
        """
        Args:
            logger: El del caso de uso, para que sus avisos salgan con su nombre
        """
        self._uow = uow
        self._user_uow = user_uow
        self._email_service = email_service
        self._actividad = actividad
        self._plazo = plazo
        self._logger = logger

    async def enviar(
        self, peticion: Peticion, destinatario_de: ResolverDestinatario
    ) -> InvitationResponseDTO:
        """
        Crea y guarda la invitación, avisa y manda el correo.

        Args:
            peticion: Quién invita, a qué competición y con qué mensaje
            destinatario_de: Con la competición ya bloqueada y comprobada,
                resuelve a quién va (y lanza lo que no deja invitarle)

        Raises:
            Las del organizador, el estado, el plazo, el cupo, el freno por hora y
            la pendiente duplicada (una pendiente ya caducada no cuenta), y las de
            `destinatario_de`
        """
        async with self._uow:
            competition_id = CompetitionId(peticion.competition_ref)
            competition = await self._competicion_que_admite_invitar(competition_id, peticion)

            destinatario = await destinatario_de(competition)

            # Solo mientras queden plazas (BE #359): libres = max_players menos
            # aprobadas. Antes se invitaba a un torneo lleno y quien llegaba tarde
            # se enteraba al aceptar, sin haber hecho nada mal. Las pendientes no
            # ocupan plaza: cuando una acepta y llena la ultima, las demas se quedan
            # sin plaza (ver RespondToInvitationUseCase)
            # Con franjas, el cupo es de sus plazas: aquí no se mira (28 oct 2026)
            await exigir_sitio(self._uow, competition)

            await self._frenos_por_hora(competition, competition_id, peticion.inviter_id)

            # Verificar no invitation PENDING duplicada
            # Una pendiente que ya caducó sin que nadie la abriera no impide
            # invitar otra vez (release social 2)
            existing_invitation, caducada = await pendiente_vigente(
                self._uow, destinatario.correo_de_la_pendiente, competition_id
            )
            if existing_invitation:
                raise DuplicateInvitationViolation(
                    # Sin el correo: el mensaje sale en el 409 (revisor de B-01)
                    "A pending invitation already exists in competition "
                    f"{peticion.competition_ref}."
                )

            # Crear invitation
            invitation = Invitation.create(
                id=InvitationId.generate(),
                competition_id=competition_id,
                inviter_id=peticion.inviter_id,
                invitee_email=destinatario.correo,
                invitee_user_id=destinatario.user_id,
                personal_message=peticion.personal_message,
                sent_by_email=destinatario.por_correo,
            )

            # Persistir
            await self._uow.invitations.add(invitation)

            # Y con la primera invitacion se abren las inscripciones (BE #319),
            # si todavía no le tocaba abrirse (una a la que ya le tocaba se abrió
            # arriba a su hora: invitar no la exime del plazo, O3). Aqui y no antes:
            # abrir y fallar luego dejaria el torneo abierto sin nadie invitado
            if CompetitionPolicy.invitation_opens_enrollment(competition.status):
                competition.activate()
                await self._uow.competitions.update(competition)

            # El nombre que usa en ESTA competición (#710), también en el correo
            legal = bool(
                await quieren_su_nombre_legal(self._uow, [(competition_id, peticion.inviter_id)])
            )

        # Ya guardada: si tiene cuenta, le sale en Actividad (BE-2)
        await self._avisar(competition, invitation, caducada)

        async with self._user_uow:
            # Tambien en el correo: es un aviso de que alguien te ha invitado, y
            # a ese alguien lo reconoces por como aparece en la competicion
            inviter_user = await self._user_uow.users.find_by_id(peticion.inviter_id)
            inviter_name = nombre_de_quien_invita(inviter_user, legal)

        # Enviar email de invitacion (fuera de la transaccion, no bloquea la creacion)
        await self._enviar_el_correo(
            destinatario.correo_del_aviso or invitation.invitee_email,
            destinatario.nombre,
            inviter_name,
            competition,
            invitation,
        )

        return _respuesta(invitation, competition, inviter_name, destinatario.nombre)

    async def _competicion_que_admite_invitar(
        self, competition_id: CompetitionId, peticion: Peticion
    ) -> Competition:
        """
        La competición, bloqueada, si quien invita la organiza y aún se puede invitar.

        Raises:
            CompetitionNotFoundError, NotCompetitionCreatorError y las del estado,
            el plazo y los equipos formados
        """
        # Buscar competition
        # Con la fila bloqueada (BE #359): una inscripcion que llena la ultima
        # plaza entre comprobar el cupo y guardar dejaba una pendiente nueva en
        # un torneo lleno. Mismo orden que las inscripciones
        competition = await self._uow.competitions.find_by_id_for_update(competition_id)
        if not competition:
            raise CompetitionNotFoundError(f"Competition not found: {peticion.competition_ref}")

        # Verificar creator/admin
        if not peticion.is_admin and not competition.is_creator(peticion.inviter_id):
            raise NotCompetitionCreatorError("Only the competition creator can send invitations.")

        # Una programada a la que ya le tocaba se abre a su hora, no ahora:
        # abrirla tarde no la exime del plazo (F7, 16 nov 2026)
        await EnrollmentOpener.abrir_las_que_toquen(
            [competition], self._uow, self._plazo.zonas if self._plazo else None
        )
        # Validar estado de competicion
        CompetitionPolicy.can_send_invitation(competition.status)
        # Pasado el plazo, aunque siga abierta, no (C2). Una programada se abrió
        # justo antes a su hora, así que tampoco: invitar no la exime (O3)
        await exigir_el_plazo(self._plazo, competition)
        # Con los equipos formados, solo si al aceptarla se pueden deshacer (sin
        # partidos), y nunca con la sala de draft abierta (B3, 15 nov 2026)
        await exigir_que_se_pueda_invitar(self._uow, competition)
        return competition

    async def _frenos_por_hora(
        self, competition: Competition, competition_id: CompetitionId, inviter_id: UserId
    ) -> None:
        """
        Rate limit (min(max_players, MAX_INVITATIONS_PER_HOUR) por hora), despues
        de las plazas: una competicion llena con el freno agotado decia «espera»
        cuando lo cierto es que ya no cabe nadie.
        """
        one_hour_ago = ahora_utc_sin_zona() - timedelta(hours=1)
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

    async def _enviar_el_correo(
        self,
        to_email: str,
        invitee_name: str | None,
        inviter_name: str,
        competition: Competition,
        invitation: Invitation,
    ) -> None:
        """El correo de la invitación; si falla, se apunta y la invitación sigue."""
        if not self._email_service:
            return
        try:
            await self._email_service.send_invitation_email(
                to_email=to_email,
                invitee_name=invitee_name,
                inviter_name=inviter_name,
                competition_name=str(competition.name),
                personal_message=invitation.personal_message,
                expires_at=invitation.expires_at,
            )
        except Exception as e:
            self._logger.warning(
                "Failed to send invitation email to %s: %s",
                _mask_email(to_email),
                str(e),
            )


def _respuesta(
    invitation: Invitation,
    competition: Competition,
    inviter_name: str,
    invitee_name: str | None,
) -> InvitationResponseDTO:
    """
    Al organizador, el nombre de quien eligió o solo el correo que tecleó
    mientras no responda; nunca un correo que no escribió él (B-01, B-03).
    """
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
