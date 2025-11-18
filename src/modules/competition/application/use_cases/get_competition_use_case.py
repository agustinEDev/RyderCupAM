# -*- coding: utf-8 -*-
"""
Caso de Uso: Obtener Competition.

Permite obtener los detalles de una competición por su ID.
"""

from src.modules.competition.application.dto.competition_dto import (
    CompetitionResponseDTO,
)
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
    ) -> CompetitionResponseDTO:
        """
        Ejecuta el caso de uso de consulta de competición.

        Args:
            competition_id: ID de la competición a consultar

        Returns:
            DTO con los datos completos de la competición

        Raises:
            CompetitionNotFoundError: Si la competición no existe
        """
        async with self._uow:
            # 1. Buscar la competición
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {competition_id.value}"
                )

            # 2. Convertir a DTO
            # El DTO tiene validadores que convierten los Value Objects
            return CompetitionResponseDTO(
                id=competition.id,
                creator_id=competition.creator_id,
                name=competition.name,
                status=competition.status,
                start_date=competition.dates.start_date,
                end_date=competition.dates.end_date,
                location={
                    "main_country": competition.location.main_country.value,
                    "adjacent_country_1": (
                        competition.location.adjacent_country_1.value
                        if competition.location.adjacent_country_1
                        else None
                    ),
                    "adjacent_country_2": (
                        competition.location.adjacent_country_2.value
                        if competition.location.adjacent_country_2
                        else None
                    ),
                },
                handicap_settings={
                    "type": competition.handicap_settings.type.value,
                    "percentage": competition.handicap_settings.percentage,
                },
                max_players=competition.max_players,
                team_assignment=competition.team_assignment,
                created_at=competition.created_at,
                updated_at=competition.updated_at,
            )
