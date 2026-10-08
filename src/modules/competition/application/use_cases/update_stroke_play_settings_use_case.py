"""
Caso de Uso: Cambiar los ajustes del stroke play (RyderCupAM#251).

Categorías, jornadas por jugador y regla de la general de un Stableford o un
Medal, hasta que se cierran las inscripciones: ahí se fija el hándicap de cada
jugador y su categoría (decidido el 7 oct 2026, como hace la RFEG).
"""

from uuid import UUID

from src.modules.competition.application.dto.competition_dto import (
    StrokePlaySettingsDTO,
    StrokePlaySettingsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.stroke_play_setup import (
    StrokePlaySettingsError,
)
from src.modules.user.domain.value_objects.user_id import UserId


class UpdateStrokePlaySettingsUseCase:
    """Cambia los ajustes del stroke play; lo que no llega no se toca."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self,
        competition_id: UUID,
        request: StrokePlaySettingsDTO,
        user_id: UserId,
        is_admin: bool = False,
    ) -> StrokePlaySettingsResponseDTO:
        """
        Args:
            competition_id: La competición
            request: Lo que cambia
            user_id: Quien lo pide: el creador o un admin

        Returns:
            Los ajustes como quedan

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si no lo pide el creador ni un admin
            TournamentTypeError: Si es una Ryder
            CompetitionStateError: Si ya ha empezado
            StrokePlaySettingsError: Si los ajustes no tienen sentido
        """
        async with self._uow:
            # Bloqueada, como la lee el primer golpe al arrancarla: al arrancar se fijan
            # las categorías, y unos límites cambiados a la vez las dejarían sin sentido
            competition = await self._uow.competitions.find_by_id_for_update(
                CompetitionId(competition_id)
            )
            if not competition:
                raise CompetitionNotFoundError(f"No existe competición con ID {competition_id}")

            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el creador puede cambiar los ajustes de la competición"
                )

            # Bajar el cupo de jornadas no puede dejar a nadie sin una de las suyas (#251)
            if request.max_matchdays_per_player is not None:
                await self._comprobar_jornadas(competition.id, request.max_matchdays_per_player)

            ajustes = competition.update_stroke_play(
                category_limits=request.category_limits,
                max_matchdays_per_player=request.max_matchdays_per_player,
                overall_standing=request.overall_standing,
            )
            await self._uow.competitions.update(competition)

        return CompetitionDTOMapper.to_stroke_play_dto(ajustes)

    async def _comprobar_jornadas(self, competition_id: CompetitionId, maximo: int) -> None:
        """
        Raises:
            StrokePlaySettingsError: Si alguien ya juega más jornadas que el nuevo máximo
        """
        sesiones = {s.id: s for s in await self._uow.rounds.find_by_competition(competition_id)}
        por_jugador: dict = {}
        for plaza in await self._uow.plazas.de_la_competicion(competition_id):
            por_jugador.setdefault(plaza.user_id, set()).add(sesiones[plaza.round_id].round_date)
        mas = max((len(dias) for dias in por_jugador.values()), default=0)
        if mas > maximo:
            raise StrokePlaySettingsError(
                f"Hay jugadores que ya juegan {mas} jornadas: quítales franjas antes de "
                f"bajar el máximo a {maximo}."
            )
