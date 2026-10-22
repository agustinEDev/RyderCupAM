"""
Avisar a Actividad sin que un fallo tumbe la accion (BE-2, G27).

Cada caso de uso avisa despues de guardar lo suyo. El feed es accesorio y la
accion no: si avisar falla, la solicitud sigue aprobada y el partido cerrado.
Se deja constancia en el log y se sigue.
"""

import logging
from collections.abc import Awaitable, Callable, Sequence

from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class AvisosDeActividad(CompetitionActivityPublisherInterface):
    """
    El puerto, con red: sin publicador no hace nada, y lo que falle al avisar
    se queda en un WARNING.
    """

    def __init__(self, publisher: CompetitionActivityPublisherInterface | None):
        self._publisher = publisher

    async def _avisar(
        self, que: str, aviso: Callable[[CompetitionActivityPublisherInterface], Awaitable[None]]
    ) -> None:
        if self._publisher is None:
            return
        try:
            await aviso(self._publisher)
        except Exception:
            logger.warning("Could not publish activity notice %s", que, exc_info=True)

    async def enrolled(
        self, competition: Competition, enrollment: Enrollment, accepted_request: bool
    ) -> None:
        await self._avisar(
            "enrolled",
            lambda p: p.enrolled(competition, enrollment, accepted_request),
        )

    async def left(self, competition_id: CompetitionId, user_id: UserId) -> None:
        await self._avisar("left", lambda p: p.left(competition_id, user_id))

    async def cancelled(self, competition_id: CompetitionId) -> None:
        await self._avisar("cancelled", lambda p: p.cancelled(competition_id))

    async def invited(self, competition: Competition, invitation: Invitation) -> None:
        # Sin cuenta no hay Actividad donde avisar: le llega el correo
        if invitation.invitee_user_id is None:
            return
        await self._avisar("invited", lambda p: p.invited(competition, invitation))

    async def invitation_withdrawn(self, invitation: Invitation) -> None:
        if invitation.invitee_user_id is None:
            return
        await self._avisar("invitation_withdrawn", lambda p: p.invitation_withdrawn(invitation))

    async def invitation_answered(self, invitation: Invitation) -> None:
        # Sin cuenta al invitarle no hubo aviso que retirar
        if invitation.invitee_user_id is None:
            return
        await self._avisar("invitation_answered", lambda p: p.invitation_answered(invitation))

    async def invitations_closed(self, invitations: Sequence[Invitation]) -> None:
        # Solo las de quien tenia cuenta: las demas no tuvieron aviso
        con_aviso = [i for i in invitations if i.invitee_user_id is not None]
        if not con_aviso:
            return
        await self._avisar("invitations_closed", lambda p: p.invitations_closed(con_aviso))

    async def requests_closed(
        self, competition: Competition, enrollments: Sequence[Enrollment]
    ) -> None:
        if not enrollments:
            return
        await self._avisar("requests_closed", lambda p: p.requests_closed(competition, enrollments))

    async def request_rejected(self, competition: Competition, enrollment: Enrollment) -> None:
        await self._avisar(
            "request_rejected", lambda p: p.request_rejected(competition, enrollment)
        )

    async def match_finished(self, competition: Competition, round_: Round, match: Match) -> None:
        await self._avisar("match_finished", lambda p: p.match_finished(competition, round_, match))

    async def completed(self, competition: Competition) -> None:
        await self._avisar("completed", lambda p: p.completed(competition))

    async def reopened(self, competition_id: CompetitionId) -> None:
        await self._avisar("reopened", lambda p: p.reopened(competition_id))

    async def made_private(self, competition_id: CompetitionId) -> None:
        await self._avisar("made_private", lambda p: p.made_private(competition_id))

    async def deleted(self, competition_id: CompetitionId) -> None:
        await self._avisar("deleted", lambda p: p.deleted(competition_id))
