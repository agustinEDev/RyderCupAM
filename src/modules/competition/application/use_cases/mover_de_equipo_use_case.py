"""
Caso de Uso: Meter a un jugador en un equipo de la Ryder, o cambiarle (release social 3, T3).

Desde el 28 oct 2026 entrar o salir ya no deshace los equipos: quien entra queda
sin equipo y el organizador le coloca, y si sale alguien el organizador
reequilibra. Solo el organizador o un admin, con los equipos formados, sin
partidos y antes de empezar; nunca a un capitán. Los sobres vuelven a borrador
y a los capitanes se les avisa.
"""

from src.modules.competition.application.dto.round_match_dto import (
    MoverDeEquipoRequestDTO,
    MoverDeEquipoResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.services import equipos_que_cambian
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.baja_de_la_competicion import (
    exigir_sin_draft_abierto,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class MoverDeEquipoUseCase:
    """El organizador pone a un jugador en A o en B."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """
        Args:
            actividad: Para avisar a los capitanes de que sus equipos cambiaron (T4)
        """
        self._uow = uow
        self._actividad = AvisosDeActividad(actividad)

    async def execute(
        self, request: MoverDeEquipoRequestDTO, quien: UserId, is_admin: bool = False
    ) -> MoverDeEquipoResponseDTO:
        """
        Raises:
            CompetitionNotFoundError: Si no existe
            NotCompetitionCreatorError: Si no la organiza ni es admin
            DraftInProgressError: Con la sala de draft abierta
            TeamsLockedError: Sin equipos, con partidos, empezada o sin ese inscrito
            CaptainCannotMoveError: Si es capitán
        """
        async with self._uow:
            competition = await self._uow.competitions.find_by_id_for_update(
                CompetitionId(request.competition_id)
            )
            if competition is None:
                raise CompetitionNotFoundError(f"No existe la competición {request.competition_id}")
            if not is_admin and not competition.is_creator(quien):
                raise NotCompetitionCreatorError("Solo el organizador cambia a alguien de equipo")
            await exigir_sin_draft_abierto(self._uow, competition.id)
            capitanes = await equipos_que_cambian.mover(
                self._uow, competition, UserId(request.user_id), request.team
            )
            reparto = await self._uow.team_assignments.find_by_competition(competition.id)
        await self._actividad.teams_changed(competition, capitanes)
        return MoverDeEquipoResponseDTO(
            team_a_player_ids=[u.value for u in reparto.team_a_player_ids] if reparto else [],
            team_b_player_ids=[u.value for u in reparto.team_b_player_ids] if reparto else [],
        )
