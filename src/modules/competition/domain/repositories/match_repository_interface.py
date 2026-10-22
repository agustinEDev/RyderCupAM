"""Match Repository Interface - Domain Layer."""

from abc import ABC, abstractmethod
from collections.abc import Collection, Sequence

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.match import Match
from ..value_objects.match_id import MatchId
from ..value_objects.match_status import MatchStatus
from ..value_objects.round_id import RoundId


class MatchRepositoryInterface(ABC):
    """Interfaz para el repositorio de partidos."""

    @abstractmethod
    async def add(self, match: Match) -> None:
        """Agrega un nuevo partido."""
        pass

    @abstractmethod
    async def update(self, match: Match) -> None:
        """Actualiza un partido existente."""
        pass

    @abstractmethod
    async def find_by_id(self, match_id: MatchId) -> Match | None:
        """Busca un partido por su ID."""
        pass

    @abstractmethod
    async def find_by_id_for_update(self, match_id: MatchId) -> Match | None:
        """
        Busca un partido por su ID bloqueando su fila (SELECT ... FOR UPDATE).

        Lo usa la apertura automatica de la anotacion (BE #305): dos jugadores
        pueden mandar su primer golpe a la vez, y sin bloqueo los dos abririan
        el partido y duplicarian los 18 hoyos por jugador.
        """
        pass

    @abstractmethod
    async def find_completed_for_player(
        self, user_id: UserId, limit: int | None = None
    ) -> list[Match]:
        """
        Partidos terminados en los que el usuario jugó, del más reciente al más
        antiguo por fecha de la ronda.

        Alimenta las estadísticas e historial del jugador (BE #128). Solo
        cuenta lo terminado: un partido a medias todavía no dice cómo quedó.
        """
        pass

    @abstractmethod
    async def find_by_round(self, round_id: RoundId) -> list[Match]:
        """Busca todos los partidos de una ronda."""
        pass

    @abstractmethod
    async def find_by_rounds_for_player(
        self, round_ids: Sequence[RoundId], user_id: UserId
    ) -> list[Match]:
        """Los partidos de un jugador en varias rondas, en una sola lectura (FE #846)."""
        pass

    @abstractmethod
    async def find_by_round_for_update(self, round_id: RoundId) -> list[Match]:
        """
        Los partidos de una ronda con sus filas bloqueadas (SELECT ... FOR UPDATE).

        Lo usa el borrado de competiciones (BE #347): conceder o terminar un
        partido no bloquea la competición, y sin esto uno concedido a la vez que
        se borra se iría en la cascada.
        """
        pass

    @abstractmethod
    async def delete(self, match_id: MatchId) -> bool:
        """Elimina un partido. Retorna True si existia."""
        pass

    @abstractmethod
    async def find_with_both_players(
        self, user_id: UserId, other_id: UserId, statuses: Collection[MatchStatus]
    ) -> list[Match]:
        """Los partidos en esos estados donde juegan los dos, en cualquier bando."""
        pass

    @abstractmethod
    async def find_finished_for_players(self, user_ids: Collection[UserId]) -> list[Match]:
        """
        Todos los partidos acabados (terminados, concedidos o por
        incomparecencia) en los que jugo alguno de ellos, sin tope ni orden,
        en una sola lectura: el historial de campos tiene que ver hasta lo mas
        antiguo, y un concedido con hoyos jugados tambien piso el campo
        (logros exclusivos, 22 oct 2026). Sin jugadores, ninguno.
        """
