"""Repositorio: las plazas de los jugadores en las franjas de stroke play (#251)."""

from abc import ABC, abstractmethod

from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class PlazaEnFranjaRepositoryInterface(ABC):
    """Una plaza por jugador y franja."""

    @abstractmethod
    async def add(self, plaza: PlazaEnFranja) -> None:
        """Guarda una plaza nueva."""

    @abstractmethod
    async def quitar(self, round_id: RoundId, user_id: UserId) -> None:
        """Quita la plaza de ese jugador en esa franja, si la tiene."""

    @abstractmethod
    async def quitar_del_jugador(self, competition_id: CompetitionId, user_id: UserId) -> None:
        """Quita todas las plazas de ese jugador en esa competición (al retirarse)."""

    @abstractmethod
    async def de_la_competicion(self, competition_id: CompetitionId) -> list[PlazaEnFranja]:
        """Todas las plazas de la competición, por orden de llegada."""
