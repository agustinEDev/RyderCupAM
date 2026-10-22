"""Adaptador: si una invitacion se puede aceptar lo dice el modulo de competicion."""

from collections.abc import Callable, Sequence
from datetime import datetime

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.invitation_id import (
    InvalidInvitationIdError,
    InvitationId,
)
from src.modules.social.application.ports.invitation_availability_interface import (
    InvitationAvailabilityInterface,
)


class InvitationAvailabilityAdapter(InvitationAvailabilityInterface):
    """
    Pregunta por todas las invitaciones de una pagina de una vez.

    El reloj es el de la propia invitacion (`Invitation.is_expired`, hora local
    sin zona): con otro, una invitacion se veria caducada en el feed y viva al
    aceptarla, o al reves.
    """

    def __init__(
        self,
        competition_uow: CompetitionUnitOfWorkInterface,
        reloj: Callable[[], datetime] = datetime.now,
    ):
        self._competition_uow = competition_uow
        self._reloj = reloj

    async def closed_ids(self, invitation_ids: Sequence[str]) -> set[str]:
        legibles: dict[str, InvitationId] = {}
        for crudo in invitation_ids:
            try:
                legibles[crudo] = InvitationId(crudo)
            except (TypeError, ValueError, InvalidInvitationIdError):
                continue
        abiertas: set[InvitationId] = set()
        if legibles:
            async with self._competition_uow:
                abiertas = await self._competition_uow.invitations.find_acceptable_ids(
                    list(legibles.values()), self._reloj()
                )
        # Un id ilegible no es una invitacion que se pueda aceptar
        return {
            crudo
            for crudo in invitation_ids
            if crudo not in legibles or legibles[crudo] not in abiertas
        }
