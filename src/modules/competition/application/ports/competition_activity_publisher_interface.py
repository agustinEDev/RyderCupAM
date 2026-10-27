"""Puerto: contar en Actividad lo que pasa en una competicion."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class TeeTimeAssignment:
    """
    La salida de un jugador en una ronda: cuando sale y con quien (G1-G3).

    En stroke play, la hora de su partida y sus compañeros de grupo; en una
    Ryder, el partido —sin hora: la sesion es mañana, tarde o noche—, con su
    compañero si lo hay y sus rivales.

    `changed` dice si sustituye a una salida que ya tenia en esa ronda.
    `out_of_play`: no se presento o se retiro; sigue en su grupo, que es el
    asignado, pero su aviso no se toca ni se le manda otro.
    `match_id` no cuenta para saber si cambio: regenerar los mismos
    emparejamientos crea partidos nuevos y, para el jugador, nada cambia.
    """

    user_id: UserId
    round_date: date
    session_type: SessionType
    tee_time: time | None
    partner_ids: tuple[UserId, ...]
    opponent_ids: tuple[UserId, ...]
    match_id: MatchId | None = None
    changed: bool = False
    out_of_play: bool = False

    def same_slot_as(self, other: "TeeTimeAssignment") -> bool:
        """Si para el jugador es la misma salida: dia, sesion, hora, compañeros y rivales."""
        return (
            self.round_date == other.round_date
            and self.session_type == other.session_type
            and self.tee_time == other.tee_time
            and set(self.partner_ids) == set(other.partner_ids)
            and set(self.opponent_ids) == set(other.opponent_ids)
        )


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
    async def removed(self, competition: Competition, enrollment: Enrollment) -> None:
        """El organizador quita a un inscrito: se le avisa solo a el (release social 2)."""

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

    @abstractmethod
    async def round_deleted(self, competition_id: CompetitionId, round_id: RoundId) -> None:
        """
        Una ronda se borra: lo que Actividad guardaba de ella (sus avisos de
        salida y los que se retiraron por un cambio) ya no sirve.
        """

    @abstractmethod
    async def tee_times(
        self,
        competition: Competition,
        round_id: RoundId,
        assigned: Sequence[TeeTimeAssignment],
        withdrawn: Sequence[UserId],
    ) -> None:
        """
        Las salidas de una ronda cambiaron (G1-G4): `assigned`, las nuevas o
        cambiadas segun esta accion; `withdrawn`, quienes se quedan sin salida
        en ella. Se llama solo si a alguien le cambia algo.

        Quien publica no tiene por que fiarse de esa foto: las publicaciones van
        tras su commit y sin orden garantizado, y la de una accion vieja puede
        llegar la ultima. El adaptador de Actividad relee la ronda con ella
        bloqueada y compara con lo ya publicado (revision del 22 oct 2026).
        """
