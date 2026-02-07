"""
Caso de Uso: Obtener Competition.

Permite obtener los detalles de una competicion por su ID.
"""

from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


class GetCompetitionUseCase:
    """
    Caso de uso para obtener una competicion por su ID.

    Este es un caso de uso de consulta (query), no modifica estado.
    Cualquier usuario puede consultar una competicion.

    Orquesta:
    1. Buscar la competicion por ID
    2. Retornar la entidad (la conversion a DTO es responsabilidad de la capa de presentacion)
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(self, competition_id: CompetitionId) -> Competition | None:
        """
        Ejecuta el caso de uso de consulta de competicion.

        Retorna la entidad Competition directamente.

        Args:
            competition_id: ID de la competicion a consultar

        Returns:
            Competition: Entidad de la competicion

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
        """
        async with self._uow:
            # Buscar la competicion
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {competition_id.value}"
                )

            return competition
