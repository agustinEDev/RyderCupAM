"""Match Repository Interface - Domain Layer."""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.match import Match
from ..value_objects.match_id import MatchId
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
    async def delete(self, match_id: MatchId) -> bool:
        """Elimina un partido. Retorna True si existia."""
        pass
