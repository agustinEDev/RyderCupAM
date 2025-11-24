# -*- coding: utf-8 -*-
"""
Caso de Uso: Obtener Competition.

Permite obtener los detalles de una competición por su ID.
"""

from typing import Optional
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""
    pass


class GetCompetitionUseCase:
    """
    Caso de uso para obtener una competición por su ID.

    Este es un caso de uso de consulta (query), no modifica estado.
    Cualquier usuario puede consultar una competición.

    Orquesta:
    1. Buscar la competición por ID
    2. Retornar la entidad (la conversión a DTO es responsabilidad de la capa de presentación)
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self,
        competition_id: CompetitionId
    ) -> Optional[Competition]:
        """
        Ejecuta el caso de uso de consulta de competición.

        Retorna la entidad Competition directamente.

        Args:
            competition_id: ID de la competición a consultar

        Returns:
            Competition: Entidad de la competición

        Raises:
            CompetitionNotFoundError: Si la competición no existe
        """
        async with self._uow:
            # Buscar la competición
            competition = await self._uow.competitions.find_by_id(competition_id)
            
            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {competition_id.value}"
                )

            return competition
