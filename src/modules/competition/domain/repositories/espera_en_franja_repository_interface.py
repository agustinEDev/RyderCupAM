"""Repositorio: las listas de espera de las franjas de stroke play (#251)."""

from abc import ABC, abstractmethod

from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class EsperaEnFranjaRepositoryInterface(ABC):
    """Una espera por jugador y franja, por orden de llegada."""

    @abstractmethod
    async def add(self, espera: EsperaEnFranja) -> None:
        """Al final de la lista."""

    @abstractmethod
    async def quitar(self, round_id: RoundId, user_id: UserId) -> None:
        """Lo saca de esa lista, si estaba."""

    @abstractmethod
    async def de_la_competicion(self, competition_id: CompetitionId) -> list[EsperaEnFranja]:
        """Todas las esperas de la competición, por orden de llegada."""

    @abstractmethod
    async def vaciar(self, competition_id: CompetitionId) -> None:
        """Vacía todas las listas de la competición (al cerrar las inscripciones)."""
