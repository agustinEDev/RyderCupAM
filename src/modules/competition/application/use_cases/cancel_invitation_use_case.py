"""
Caso de uso: retirar una invitacion pendiente (BE #359).

Antes no habia forma: quien invitaba a la persona equivocada solo podia esperar
los 7 dias a que caducara. La retiran el organizador, quien la envio o un admin;
queda CANCELLED y el invitado no recibe aviso.
"""

from uuid import UUID

from src.modules.competition.application.exceptions import (
    InvitationNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.user.domain.value_objects.user_id import UserId


class CancelInvitationUseCase:
    """Retira una invitacion pendiente."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, invitation_id: UUID, user_id: UUID, is_admin: bool = False) -> None:
        """
        Raises:
            InvitationNotFoundError: Si la invitacion no existe
            NotCompetitionCreatorError: Si quien la retira no es el organizador,
                quien la envio ni un admin
            InvalidInvitationStatusViolation: Si ya no esta pendiente
        """
        async with self._uow:
            id_ = InvitationId(invitation_id)
            invitation = await self._uow.invitations.find_by_id(id_)
            if not invitation:
                raise InvitationNotFoundError(f"Invitation not found: {invitation_id}")

            # Bloqueadas, y en este orden: la competicion y despues la invitacion,
            # como aceptarla. Sin bloqueo, retirar y aceptar a la vez leian las dos
            # PENDING y quedaba un jugador inscrito con la invitacion retirada
            # (CodeRabbit en la #488). Se decide con lo leido ya bloqueado
            competition = await self._uow.competitions.find_by_id_for_update(
                invitation.competition_id
            )
            invitation = await self._uow.invitations.find_by_id_for_update(id_)
            if not invitation:
                raise InvitationNotFoundError(f"Invitation not found: {invitation_id}")

            quien = UserId(user_id)
            es_el_organizador = competition is not None and competition.is_creator(quien)
            if not is_admin and invitation.inviter_id != quien and not es_el_organizador:
                raise NotCompetitionCreatorError(
                    "Only the competition creator or whoever sent it can cancel an invitation."
                )

            # Una que caduco sin que nadie la pasara a EXPIRED no se retira: se
            # quedo sin respuesta, y asi debe constar
            invitation.check_expiration()
            if not invitation.is_pending():
                await self._uow.invitations.update(invitation)
                no_pendiente = invitation.status.value
            else:
                invitation.cancel()
                await self._uow.invitations.update(invitation)
                no_pendiente = None

        # Fuera del `async with`: el paso a EXPIRED se guarda, y luego se dice
        if no_pendiente:
            raise InvalidInvitationStatusViolation(
                f"Invitation is in status {no_pendiente}. Only PENDING invitations can be cancelled."
            )
