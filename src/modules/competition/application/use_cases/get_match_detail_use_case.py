"""Caso de Uso: Obtener detalle de un partido."""

from src.modules.competition.application.dto.round_match_dto import (
    GetMatchDetailRequestDTO,
    GetMatchDetailResponseDTO,
    MatchPlayerResponseDTO,
)
from src.modules.competition.application.exceptions import MatchNotFoundError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.match_id import MatchId


class GetMatchDetailUseCase:
    """
    Caso de uso para obtener el detalle completo de un partido.

    Incluye información de la ronda (fecha, tipo, formato)
    junto con los datos del partido.

    Accesible por cualquier usuario (lectura).
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, request: GetMatchDetailRequestDTO) -> GetMatchDetailResponseDTO:
        async with self._uow:
            # 1. Buscar el partido
            match_id = MatchId(request.match_id)
            match = await self._uow.matches.find_by_id(match_id)

            if not match:
                raise MatchNotFoundError(f"No existe partido con ID {request.match_id}")

            # 2. Buscar la ronda para info adicional
            round_entity = await self._uow.rounds.find_by_id(match.round_id)

        # 3. Construir respuesta
        return GetMatchDetailResponseDTO(
            id=match.id.value,
            round_id=match.round_id.value,
            match_number=match.match_number,
            team_a_players=[
                MatchPlayerResponseDTO(
                    user_id=p.user_id.value,
                    playing_handicap=p.playing_handicap,
                    tee_category=p.tee_category.value,
                    strokes_received=list(p.strokes_received),
                )
                for p in match.team_a_players
            ],
            team_b_players=[
                MatchPlayerResponseDTO(
                    user_id=p.user_id.value,
                    playing_handicap=p.playing_handicap,
                    tee_category=p.tee_category.value,
                    strokes_received=list(p.strokes_received),
                )
                for p in match.team_b_players
            ],
            status=match.status.value,
            handicap_strokes_given=match.handicap_strokes_given,
            strokes_given_to_team=match.strokes_given_to_team,
            result=match.result,
            round_date=round_entity.round_date if round_entity else None,
            session_type=round_entity.session_type.value if round_entity else None,
            match_format=round_entity.match_format.value if round_entity else None,
            created_at=match.created_at,
            updated_at=match.updated_at,
        )
