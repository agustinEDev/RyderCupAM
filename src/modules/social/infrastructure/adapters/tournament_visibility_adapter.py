"""Adaptador: la visibilidad de los torneos sale del modulo de competicion."""

from collections.abc import Sequence

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import (
    CompetitionId,
    InvalidCompetitionIdError,
)
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.social.application.ports.tournament_visibility_interface import (
    TournamentVisibilityInterface,
)


class TournamentVisibilityAdapter(TournamentVisibilityInterface):
    """Lee los torneos de una pagina de una vez y dice cuales son privados ahora."""

    def __init__(self, competition_uow: CompetitionUnitOfWorkInterface):
        self._competition_uow = competition_uow

    async def private_ids(self, competition_ids: Sequence[str]) -> set[str]:
        legibles = []
        for crudo in competition_ids:
            # El `payload` es JSONB: un id ilegible no puede tumbar el feed
            try:
                legibles.append(CompetitionId(crudo))
            except (TypeError, ValueError, InvalidCompetitionIdError):
                continue
        if not legibles:
            return set()
        # Solo la visibilidad: el agregado entero cargaria todas sus relaciones
        async with self._competition_uow:
            visibilidades = await self._competition_uow.competitions.find_visibilities(legibles)
        return {
            str(competition_id.value)
            for competition_id, visibilidad in visibilidades.items()
            if visibilidad != Visibility.PUBLIC
        }
