# -*- coding: utf-8 -*-
"""In-Memory Competition Repository para testing."""

from typing import Dict, List, Optional
from datetime import date

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_repository_interface import (
    CompetitionRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryCompetitionRepository(CompetitionRepositoryInterface):
    """
    Implementación en memoria del repositorio de competiciones para testing.
    """

    def __init__(self):
        self._competitions: Dict[CompetitionId, Competition] = {}

    async def add(self, competition: Competition) -> None:
        """Agrega una nueva competición."""
        self._competitions[competition.id] = competition

    async def update(self, competition: Competition) -> None:
        """Actualiza una competición existente."""
        if competition.id in self._competitions:
            self._competitions[competition.id] = competition

    async def save(self, competition: Competition) -> None:
        """Guarda o actualiza una competición (alias para compatibilidad)."""
        self._competitions[competition.id] = competition

    async def find_by_id(self, competition_id: CompetitionId) -> Optional[Competition]:
        """Busca una competición por su ID."""
        return self._competitions.get(competition_id)

    async def find_by_creator(self, creator_id: UserId) -> List[Competition]:
        """Busca todas las competiciones creadas por un usuario."""
        return [
            comp for comp in self._competitions.values()
            if comp.creator_id == creator_id
        ]

    async def find_by_status(self, status: CompetitionStatus) -> List[Competition]:
        """Busca todas las competiciones con un estado específico."""
        return [
            comp for comp in self._competitions.values()
            if comp.status == status
        ]

    async def find_active_in_date_range(
        self,
        start_date: date,
        end_date: date
    ) -> List[Competition]:
        """Busca competiciones activas que se solapen con un rango de fechas."""
        active_statuses = [
            CompetitionStatus.ACTIVE,
            CompetitionStatus.CLOSED,
            CompetitionStatus.IN_PROGRESS
        ]

        return [
            comp for comp in self._competitions.values()
            if comp.status in active_statuses and
            self._date_ranges_overlap(
                comp.dates.start_date,
                comp.dates.end_date,
                start_date,
                end_date
            )
        ]

    async def exists_with_name(self, name: CompetitionName, creator_id: UserId) -> bool:
        """Verifica si existe una competición con un nombre específico para un creador."""
        return any(
            comp.name == name and comp.creator_id == creator_id
            for comp in self._competitions.values()
        )

    async def delete(self, competition_id: CompetitionId) -> None:
        """Elimina una competición por su ID."""
        if competition_id in self._competitions:
            del self._competitions[competition_id]

    async def find_all(self) -> List[Competition]:
        """Retorna todas las competiciones."""
        return list(self._competitions.values())

    async def count_by_creator(self, creator_id: UserId) -> int:
        """Cuenta el total de competiciones creadas por un usuario."""
        return sum(
            1 for comp in self._competitions.values()
            if comp.creator_id == creator_id
        )

    def _date_ranges_overlap(
        self,
        start1: date,
        end1: date,
        start2: date,
        end2: date
    ) -> bool:
        """Verifica si dos rangos de fechas se solapan."""
        return start1 <= end2 and end1 >= start2
