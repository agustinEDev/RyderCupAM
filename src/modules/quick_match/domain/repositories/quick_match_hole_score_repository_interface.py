"""
QuickMatchHoleScore Repository Interface - Domain Layer.
"""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.quick_match_hole_score import QuickMatchHoleScore
from ..value_objects.quick_match_hole_score_id import QuickMatchHoleScoreId
from ..value_objects.quick_match_id import QuickMatchId


class QuickMatchHoleScoreRepositoryInterface(ABC):
    """Interfaz para el repositorio de scores por hoyo de una partida rapida."""

    @abstractmethod
    async def add(self, hole_score: QuickMatchHoleScore) -> None:
        pass

    @abstractmethod
    async def update(self, hole_score: QuickMatchHoleScore) -> None:
        pass

    @abstractmethod
    async def find_by_id(
        self, hole_score_id: QuickMatchHoleScoreId
    ) -> QuickMatchHoleScore | None:
        pass

    @abstractmethod
    async def find_by_match_hole_and_player(
        self, quick_match_id: QuickMatchId, hole_number: int, player_user_id: UserId
    ) -> QuickMatchHoleScore | None:
        """Busca el score de un jugador en un hoyo concreto (para upsert)."""
        pass

    @abstractmethod
    async def find_by_match(self, quick_match_id: QuickMatchId) -> list[QuickMatchHoleScore]:
        """Lista todos los scores registrados de una partida, ordenados por hoyo."""
        pass
