"""Caso de Uso: Obtener detalle de un partido."""

from src.modules.competition.application.dto.round_match_dto import (
    GetMatchDetailRequestDTO,
    GetMatchDetailResponseDTO,
    MatchPlayerResponseDTO,
)
from src.modules.competition.application.exceptions import MatchNotFoundError
from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.application.services.lo_jugado_de_una_privada import (
    esta_dentro,
    exigir_la_partida,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.user.domain.value_objects.user_id import UserId


class GetMatchDetailUseCase:
    """
    Caso de uso para obtener el detalle completo de un partido.

    Incluye información de la ronda (fecha, tipo, formato)
    junto con los datos del partido.

    Accesible por cualquier usuario (lectura).
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        eventos: EventosDeAmigosInterface | None = None,
    ):
        self._uow = uow
        # La llave de quien está fuera de una privada (27 oct 2026)
        self._eventos = eventos

    async def execute(
        self,
        request: GetMatchDetailRequestDTO,
        *,
        quien: UserId | None = None,
        es_admin: bool = False,
    ) -> GetMatchDetailResponseDTO:
        """
        El partido. Diciendo quién mira, con la puerta de una privada.

        Raises:
            MatchNotFoundError: Si no existe
            NoPuedeVerloError: Si es de una privada en la que no está, no juega
                en él ni tiene la llave de un amigo que juegue (27 oct 2026)
        """
        dentro, competition_id = True, None
        async with self._uow:
            # 1. Buscar el partido
            match_id = MatchId(request.match_id)
            match = await self._uow.matches.find_by_id(match_id)

            if not match:
                raise MatchNotFoundError(f"No existe partido con ID {request.match_id}")

            # 2. Buscar la ronda para info adicional
            round_entity = await self._uow.rounds.find_by_id(match.round_id)
            competition = (
                await self._uow.competitions.find_by_id(round_entity.competition_id)
                if round_entity is not None and quien is not None
                else None
            )
            if competition is not None and quien is not None:
                competition_id = competition.id
                dentro = await esta_dentro(self._uow, competition, quien, es_admin=es_admin)

        if not dentro and quien is not None and competition_id is not None:
            jugadores = [p.user_id for p in (*match.team_a_players, *match.team_b_players)]
            await exigir_la_partida(False, competition_id, quien, jugadores, self._eventos)

        # 3. Construir respuesta
        return GetMatchDetailResponseDTO(
            id=match.id.value,
            round_id=match.round_id.value,
            match_number=match.match_number,
            team_a_players=[MatchPlayerResponseDTO.from_domain(p) for p in match.team_a_players],
            team_b_players=[MatchPlayerResponseDTO.from_domain(p) for p in match.team_b_players],
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
