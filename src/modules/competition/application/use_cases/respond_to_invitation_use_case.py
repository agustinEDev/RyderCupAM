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
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.genero_obligatorio import exigir_genero
from src.modules.competition.application.services.handicap_obligatorio import exigir_handicap
from src.modules.competition.application.services.inscripcion_que_vuelve import (
    guardar_la_inscripcion,
    viva,
)
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    al_ocupar_una_plaza,
)
from src.modules.competition.application.services.nombre_de_quien_invita import (
    nombre_de_quien_invita,
    quieren_su_nombre_legal,
)
from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.domain.entities.competition import Competition
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
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        self._uow = uow
        self._user_uow = user_uow
        # Los avisos de Actividad (BE-2); sin el, no se avisa
        self._actividad = AvisosDeActividad(actividad)

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
        non_pending_status, sin_plaza = await self._cerrar_si_toca(
            invitation_id, action, current_user_id, current_user_email
        )

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
        inscrito: tuple[Competition, Enrollment] | None = None
        sin_plaza_ya: list[Invitation] = []

        async with self._uow:
            # Re-fetch para tener la entidad en la sesion actual
            invitation = await self._releer_pendiente(invitation_id)

            # Verificar current_user es invitee
            if not self._es_el_invitado(invitation, current_user_id, current_user_email):
                raise NotInviteeError("You are not the invitee of this invitation.")

            # Se decide con la invitacion releida con su fila bloqueada, y antes la
            # competicion: el mismo orden que retirar. Sin bloqueo, aceptar y
            # retirar a la vez leian las dos PENDING, y quedaba un inscrito con la
            # invitacion retirada; o rechazar pisaba una retirada (CodeRabbit, #488)
            if action == "ACCEPT":
                await self._uow.competitions.find_by_id_for_update(invitation.competition_id)
            invitation = await self._releer_pendiente(invitation_id, bloqueada=True)

            # Ejecutar accion
            if action == "ACCEPT":
                competition, enrollment, sin_plaza_ya = await self._handle_accept(
                    invitation, current_user_id
                )
                inscrito = (competition, enrollment)
                enrollment_id, competition_name = enrollment.id.value, str(competition.name)
            else:
                await self._handle_decline(invitation)

        # Ya respondida, su aviso de invitado no pide nada: se retira (tabla
        # del 22 oct 2026, C). Luego, si entro, lo de inscrito
        await self._actividad.invitation_answered(invitation)
        await self._avisar_si_entro(inscrito)
        # Si ocupo la ultima plaza, las demas pendientes se cerraron solas
        await self._actividad.invitations_closed(sin_plaza_ya)

        # Construir respuesta enriquecida
        return await self._build_response(invitation, enrollment_id, competition_name)

    async def _cerrar_si_toca(
        self,
        invitation_id: InvitationId,
        action: str,
        current_user_id: UserId,
        current_user_email: str,
    ) -> tuple[str | None, bool]:
        """
        La fase 1: si ya no esta pendiente (o caduco) se guarda tal cual, y si
        se acepta con la inscripcion cerrada se queda sin plaza. Devuelve el
        estado no pendiente y si se quedo sin plaza ahora.

        La que se cierra sola aqui se guarda y retira su aviso de invitado
        aunque la respuesta acabe en error (Agustin, 22 oct 2026).
        """
        non_pending_status = None
        sin_plaza = False
        # La que se cierra sola aqui (caducada o sin plaza): se guarda, y su
        # aviso de invitado se retira aunque la respuesta acabe en error
        cerrada_ahora: Invitation | None = None
        async with self._uow:
            invitation = await self._uow.invitations.find_by_id(invitation_id)
            if not invitation:
                raise InvitationNotFoundError(f"Invitation not found: {invitation_id.value}")

            estaba_pendiente = invitation.is_pending()
            invitation.check_expiration()

            if not invitation.is_pending():
                # Persistir el cambio de estado (ej: PENDING -> EXPIRED)
                await self._uow.invitations.update(invitation)
                non_pending_status = invitation.status.value
                if estaba_pendiente:
                    cerrada_ahora = invitation
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
                cerrada_ahora = invitation

        # Ya guardada: fuera su aviso de invitado (Agustin, 22 oct 2026)
        if cerrada_ahora is not None:
            await self._actividad.invitations_closed([cerrada_ahora])
        return non_pending_status, sin_plaza

    async def _avisar_si_entro(self, inscrito: tuple[Competition, Enrollment] | None) -> None:
        """
        Ya guardada, a Actividad: entrar por invitación no es una solicitud
        aceptada; sus amigos lo ven si el torneo es público (BE-2).
        """
        if inscrito is not None:
            await self._actividad.enrolled(*inscrito, accepted_request=False)

    async def _releer_pendiente(
        self, invitation_id: InvitationId, bloqueada: bool = False
    ) -> Invitation:
        """La invitacion de la fase 2, que tiene que seguir pendiente.

        El cierre pudo llegar entre las dos fases y dejarla sin plaza: se dice
        con su codigo, no con el generico (revision local de la BE #385). Con
        `bloqueada`, releida con su fila bloqueada: es la lectura con la que se
        decide (BE #359).
        """
        repo = self._uow.invitations
        invitation = await (
            repo.find_by_id_for_update(invitation_id)
            if bloqueada
            else repo.find_by_id(invitation_id)
        )
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

    async def _handle_accept(
        self, invitation, current_user_id: UserId
    ) -> tuple[Competition, Enrollment, list[Invitation]]:
        """
        Procesa la aceptacion de una invitacion. Retorna la competicion, la
        inscripcion y las demas pendientes que se quedaron sin plaza.
        """
        # Con la fila bloqueada: si se cierra a la vez, uno espera al otro y aquí
        # se lee el estado de verdad, no un «abierta» de antes del cierre (#710)
        competition = await self._uow.competitions.find_by_id_for_update(invitation.competition_id)
        if not competition:
            raise CompetitionNotFoundError(f"Competition not found: {invitation.competition_id}")

        CompetitionPolicy.can_accept_invitation(competition.status)

        # Sin género no se sabe desde qué barras juega (#710). Antes de aceptar:
        # la invitación se queda pendiente para cuando lo rellene
        await exigir_genero(self._user_uow.users, current_user_id, es_quien_se_apunta=True)
        # Y en un Stableford o un Medal, su hándicap: de él sale su categoría (#251)
        await exigir_handicap(
            self._user_uow.users, competition, current_user_id, es_quien_se_apunta=True
        )

        existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
            current_user_id, invitation.competition_id
        )
        # Una cerrada (rechazada, cancelada, retirada) no impide entrar: se
        # reutiliza (release social 2)
        if viva(existing_enrollment):
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

        enrollment = await guardar_la_inscripcion(
            self._uow,
            existing_enrollment,
            aprobada=True,
            competition_id=CompetitionId(invitation.competition_id.value),
            user_id=current_user_id,
        )
        # Entra con los equipos formados y sin partidos: se deshacen, como al
        # salir (decidido el 27 oct 2026); si no, se quedaba fuera de los dos
        await TeamAssignmentWriter.deshacer(self._uow, competition)
        await self._uow.invitations.update(invitation)

        cerradas = await al_ocupar_una_plaza(
            self._uow, invitation.competition_id, approved_count, competition.max_players
        )

        return competition, enrollment, cerradas

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
