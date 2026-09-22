"""
Caso de Uso: Nombrar al subcapitán de un equipo (BE #320).

Decidido el 22 sep: cada capitán elige a su subcapitán entre los de su equipo,
una vez repartidos. Si el capitán se da de baja, asciende el subcapitán, y la
competición no se queda sin capitán en ese equipo.
"""

from src.modules.competition.application.dto.competition_dto import (
    CaptaincyResponseDTO,
    NameViceCaptainRequestDTO,
)
from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.mappers.competition_mapper import (
    CompetitionDTOMapper,
)
from src.modules.competition.application.services.team_roster import TeamRoster
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class NotCaptainOrCreatorError(Exception):
    """Solo el capitan del equipo, el organizador o un admin eligen al subcapitan."""

    pass


class NameViceCaptainUseCase:
    """
    Caso de uso para nombrar al subcapitán de un equipo.

    Quién: el capitán de ese equipo, el organizador —por si un capitán no usa
    la app— o un admin. Las reglas del nombramiento —tras el draft, de su
    equipo, no el propio capitán— son de la entidad.
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: NameViceCaptainRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> CaptaincyResponseDTO:
        """
        Nombra al subcapitán.

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCaptainOrCreatorError: Si no es el capitán del equipo, el
                organizador ni un admin
            TeamsNotAssignedError: Si todavía no hay equipos
            CaptainOnWrongTeamError: Si no es de ese equipo
            CompetitionStateError: Si el torneo ya está en marcha
            ValueError: Si es el propio capitán
        """
        async with self._uow:
            # Con la fila bloqueada, como al nombrar capitanes y repartir
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )
            if not (
                is_admin
                or competition.is_creator(user_id)
                or competition.is_captain_of(request.team, user_id)
            ):
                raise NotCaptainOrCreatorError(
                    "Solo el capitán del equipo o el organizador eligen al subcapitán"
                )

            jugadores, hay_reparto = await TeamRoster.de_un_equipo(
                self._uow, competition_id, request.team
            )
            competition.name_vice_captain(
                request.team,
                UserId(request.player_id),
                team_player_ids=jugadores,
                has_teams=hay_reparto,
            )
            await self._uow.competitions.update(competition)

        return CompetitionDTOMapper.to_captaincy_dto(competition)
