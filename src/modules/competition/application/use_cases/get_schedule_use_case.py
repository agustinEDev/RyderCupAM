"""Caso de Uso: Obtener Schedule de la competición."""

from collections import defaultdict

from src.modules.competition.application.dto.round_match_dto import (
    GetScheduleRequestDTO,
    GetScheduleResponseDTO,
    MatchPlayerResponseDTO,
    MatchResponseDTO,
    RoundResponseDTO,
    ScheduleDayDTO,
    TeamAssignmentResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


class CompetitionNotFoundError(Exception):
    """La competición no existe."""

    pass


class GetScheduleUseCase:
    """
    Caso de uso para obtener el schedule completo de una competición.

    Retorna todas las rondas agrupadas por día, con sus partidos
    y la asignación de equipos.

    Accesible por cualquier usuario (lectura).
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: GetScheduleRequestDTO
    ) -> GetScheduleResponseDTO:
        async with self._uow:
            # 1. Verificar que la competición existe
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Obtener todas las rondas
            rounds = await self._uow.rounds.find_by_competition(competition_id)

            # 3. Obtener partidos para cada ronda
            total_matches = 0
            rounds_with_matches: list[tuple] = []
            for round_entity in rounds:
                matches = await self._uow.matches.find_by_round(round_entity.id)
                rounds_with_matches.append((round_entity, matches))
                total_matches += len(matches)

            # 4. Obtener asignación de equipos
            team_assignment = await self._uow.team_assignments.find_by_competition(
                competition_id
            )

        # 5. Agrupar rondas por día
        days_map = defaultdict(list)
        for round_entity, matches in rounds_with_matches:
            match_dtos = [
                MatchResponseDTO(
                    id=m.id.value,
                    round_id=m.round_id.value,
                    match_number=m.match_number,
                    team_a_players=[
                        MatchPlayerResponseDTO(
                            user_id=p.user_id.value,
                            playing_handicap=p.playing_handicap,
                            tee_category=p.tee_category.value,
                            strokes_received=list(p.strokes_received),
                        )
                        for p in m.team_a_players
                    ],
                    team_b_players=[
                        MatchPlayerResponseDTO(
                            user_id=p.user_id.value,
                            playing_handicap=p.playing_handicap,
                            tee_category=p.tee_category.value,
                            strokes_received=list(p.strokes_received),
                        )
                        for p in m.team_b_players
                    ],
                    status=m.status.value,
                    handicap_strokes_given=m.handicap_strokes_given,
                    strokes_given_to_team=m.strokes_given_to_team,
                    result=m.result,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in matches
            ]

            round_dto = RoundResponseDTO(
                id=round_entity.id.value,
                competition_id=round_entity.competition_id.value,
                golf_course_id=round_entity.golf_course_id.value,
                round_date=round_entity.round_date,
                session_type=round_entity.session_type.value,
                match_format=round_entity.match_format.value,
                status=round_entity.status.value,
                handicap_mode=round_entity.handicap_mode.value if round_entity.handicap_mode else None,
                allowance_percentage=round_entity.allowance_percentage,
                effective_allowance=round_entity.get_effective_allowance(),
                matches=match_dtos,
                created_at=round_entity.created_at,
                updated_at=round_entity.updated_at,
            )
            days_map[round_entity.round_date].append(round_dto)

        # 6. Construir días ordenados
        days = [
            ScheduleDayDTO(date=d, rounds=sorted(r, key=lambda x: x.session_type))
            for d, r in sorted(days_map.items())
        ]

        # 7. Construir respuesta de team assignment
        ta_dto = None
        if team_assignment:
            ta_dto = TeamAssignmentResponseDTO(
                id=team_assignment.id.value,
                competition_id=team_assignment.competition_id.value,
                mode=team_assignment.mode.value,
                team_a_player_ids=[uid.value for uid in team_assignment.team_a_player_ids],
                team_b_player_ids=[uid.value for uid in team_assignment.team_b_player_ids],
                created_at=team_assignment.created_at,
            )

        return GetScheduleResponseDTO(
            competition_id=request.competition_id,
            days=days,
            total_rounds=len(rounds),
            total_matches=total_matches,
            team_assignment=ta_dto,
        )
