"""Puerto: contar en Actividad lo que pasa en una competicion."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionActivityPublisherInterface(ABC):
    """
    Lo que `competition` le cuenta al feed, sin depender de el.

    Mismo reparto que los logros: aqui solo el puerto, y el adaptador del modulo
    social decide que se publica, para quien y con que detalle. Se llama
    **despues** de guardar: cada caso de uso confirma lo suyo y luego avisa, y un
    fallo al avisar no deshace nada (`AvisosDeActividad`).
    """

    @abstractmethod
    async def enrolled(
        self, competition: Competition, enrollment: Enrollment, accepted_request: bool
    ) -> None:
        """Un jugador queda inscrito; `accepted_request` si fue aprobando su solicitud."""

    @abstractmethod
    async def left(self, competition_id: CompetitionId, user_id: UserId) -> None:
        """Un inscrito deja de estarlo (se retira)."""

    @abstractmethod
    async def cancelled(self, competition_id: CompetitionId) -> None:
        """La competicion se cancela: ya no hay a que estar apuntado."""

    @abstractmethod
    async def invited(self, competition: Competition, invitation: Invitation) -> None:
        """Alguien con cuenta recibe una invitacion."""

    @abstractmethod
    async def invitation_withdrawn(self, invitation: Invitation) -> None:
        """El organizador retira una invitacion pendiente."""

    @abstractmethod
    async def invitation_answered(self, invitation: Invitation) -> None:
        """El invitado acepta o rechaza la invitacion."""

    @abstractmethod
    async def invitations_closed(self, invitations: Sequence[Invitation]) -> None:
        """
        Invitaciones que dejaron de estar pendientes solas, sin que respondan el
        invitado ni el organizador: sin plaza (NO_ROOM) o caducadas (EXPIRED).
        """

    @abstractmethod
    async def requests_closed(
        self, competition: Competition, enrollments: Sequence[Enrollment]
    ) -> None:
        """Solicitudes rechazadas solas al empezar la competicion."""

    @abstractmethod
    async def request_rejected(self, competition: Competition, enrollment: Enrollment) -> None:
        """El organizador rechaza a mano una solicitud."""

    @abstractmethod
    async def match_finished(self, competition: Competition, round_: Round, match: Match) -> None:
        """Un partido de match play termina: con tarjeta, concedido o por walkover."""

    @abstractmethod
    async def completed(self, competition: Competition) -> None:
        """La competicion termina: la clasificacion final de cada uno."""

    @abstractmethod
    async def reopened(self, competition_id: CompetitionId) -> None:
        """Una competicion terminada se reabre: su clasificacion final ya no vale."""

    @abstractmethod
    async def made_private(self, competition_id: CompetitionId) -> None:
        """La competicion pasa de publica a privada."""

    @abstractmethod
    async def deleted(self, competition_id: CompetitionId) -> None:
        """La competicion se borra."""
