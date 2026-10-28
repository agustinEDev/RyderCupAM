"""
Caso de Uso: El resumen público de una competición (release social 3, L5, 28 oct 2026).

La clasificación se abre por enlace sin sesión, y su página necesita saber qué
pintar sin la ficha, que pide sesión: si es una Ryder o un stroke play, y si es
privada para decir que solo la ven quienes participan. Solo eso: nombre, tipo,
estado, visibilidad y fechas. También de una privada: privada no es secreta.
"""

from src.modules.competition.application.dto.competition_dto import (
    CompetitionSummaryDTO,
    GetCompetitionSummaryRequestDTO,
)
from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


class GetCompetitionSummaryUseCase:
    """Lo mínimo de una competición para su página pública."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, request: GetCompetitionSummaryRequestDTO) -> CompetitionSummaryDTO:
        """
        Raises:
            CompetitionNotFoundError: Si no existe
        """
        competition_id = request.competition_id
        async with self._uow:
            competicion = await self._uow.competitions.find_by_id(CompetitionId(competition_id))
        if competicion is None:
            raise CompetitionNotFoundError(f"No existe la competición {competition_id}")
        return CompetitionSummaryDTO(
            id=competicion.id.value,
            name=str(competicion.name),
            tournament_type=competicion.tournament_type.value,
            has_teams=competicion.tournament_type.has_teams,
            status=competicion.status.value,
            visibility=competicion.visibility.value,
            start_date=competicion.dates.start_date,
            end_date=competicion.dates.end_date,
        )
