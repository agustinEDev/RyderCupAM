"""
Caso de Uso: Cubrir el puesto de un capitán (BE #320).

Si un capitán se da de baja tras el draft sin subcapitán que ascienda, su
equipo se queda sin capitán, y sin esto la competición se atascaría: repartir
de nuevo pide los dos capitanes, y nombrarlos ya no se puede con equipos.
"""

from src.modules.competition.application.dto.competition_dto import (
    CaptaincyResponseDTO,
    FillCaptainRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.mappers.competition_mapper import (
    CompetitionDTOMapper,
)
from src.modules.competition.application.services.team_roster import TeamRoster
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class FillCaptainUseCase:
    """
    Caso de uso para cubrir el puesto vacío de capitán de un equipo.

    Solo el organizador o un admin. Las reglas —tras el draft, puesto vacío, de
    su equipo— son de la entidad.
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: FillCaptainRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> CaptaincyResponseDTO:
        """
        Cubre el puesto de capitán.

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si no es el organizador ni un admin
            TeamsNotAssignedError: Si todavía no hay equipos
            CaptainsLockedError: Si el puesto no está vacío
            CaptainOnWrongTeamError: Si no es de ese equipo
            CompetitionStateError: Si el torneo ya está en marcha
        """
        async with self._uow:
            # Con la fila bloqueada, como al nombrar capitanes y repartir
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el organizador cubre el puesto de un capitán"
                )

            jugadores, hay_reparto = await TeamRoster.de_un_equipo(
                self._uow, competition_id, request.team
            )
            competition.fill_captain(
                request.team,
                UserId(request.player_id),
                team_player_ids=jugadores,
                has_teams=hay_reparto,
            )
            await self._uow.competitions.update(competition)

        return CompetitionDTOMapper.to_captaincy_dto(competition)
