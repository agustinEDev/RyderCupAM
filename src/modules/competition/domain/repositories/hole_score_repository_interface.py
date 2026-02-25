"""HoleScore Repository Interface - Domain Layer."""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.hole_score import HoleScore
from ..value_objects.match_id import MatchId


class HoleScoreRepositoryInterface(ABC):
    """Interfaz para el repositorio de hole scores."""

    @abstractmethod
    async def add(self, hole_score: HoleScore) -> None:
        """Agrega un nuevo hole score."""
        pass

    @abstractmethod
    async def add_many(self, hole_scores: list[HoleScore]) -> None:
        """Agrega multiples hole scores en batch."""
        pass

    @abstractmethod
    async def update(self, hole_score: HoleScore) -> None:
        """Actualiza un hole score existente."""
        pass

    @abstractmethod
    async def find_by_match(self, match_id: MatchId) -> list[HoleScore]:
        """Busca todos los hole scores de un partido."""
        pass

    @abstractmethod
    async def find_by_match_and_hole(
        self, match_id: MatchId, hole_number: int
    ) -> list[HoleScore]:
        """Busca los hole scores de un hoyo especifico de un partido."""
        pass

    @abstractmethod
    async def find_one(
        self, match_id: MatchId, hole_number: int, player_user_id: UserId
    ) -> HoleScore | None:
        """Busca un hole score especifico."""
        pass

    @abstractmethod
    async def find_by_match_and_player(
        self, match_id: MatchId, player_user_id: UserId
    ) -> list[HoleScore]:
        """Busca todos los hole scores de un jugador en un partido."""
        pass

    @abstractmethod
    async def delete_by_match(self, match_id: MatchId) -> int:
        """Elimina todos los hole scores de un partido. Retorna la cantidad eliminada."""
        pass
