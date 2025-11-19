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
    2. Convertir a DTO y retornar
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

        CLEAN ARCHITECTURE: Retorna la entidad de dominio, NO el DTO.
        La conversión a DTO es responsabilidad de la capa de presentación.

        Args:
            competition_id: ID de la competición a consultar

        Returns:
            Competition: Entidad de dominio o None si no existe
        """
        async with self._uow:
            # Buscar y retornar la competición (o None)
            return await self._uow.competitions.find_by_id(competition_id)
