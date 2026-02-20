"""Caso de Uso: Obtener leaderboard de una competicion."""

from src.modules.competition.application.dto.scoring_dto import (
    DecidedResultDTO,
    LeaderboardMatchDTO,
    LeaderboardPlayerDTO,
    LeaderboardResponseDTO,
)
from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.validation_status import (
    ValidationStatus,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GetLeaderboardUseCase:
    """Obtiene el leaderboard completo de una competicion."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repo: UserRepositoryInterface,
        scoring_service: ScoringService,
    ):
        self._uow = uow
        self._user_repo = user_repo
        self._scoring_service = scoring_service

    async def execute(self, competition_id_str: str) -> LeaderboardResponseDTO:
        async with self._uow:
            comp_id = CompetitionId(competition_id_str)
            competition = await self._uow.competitions.find_by_id(comp_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competicion con ID {competition_id_str}"
                )

            rounds = await self._uow.rounds.find_by_competition(comp_id)

            total_a_points = 0.0
            total_b_points = 0.0
            matches_dto = []

            # Collect all user IDs for name resolution
            all_user_ids: set[UserId] = set()

            for round_entity in rounds:
                matches = await self._uow.matches.find_by_round(round_entity.id)

                for match in matches:
                    for p in (*match.team_a_players, *match.team_b_players):
                        all_user_ids.add(p.user_id)

            # Resolve all names
            user_names = await self._resolve_user_names(list(all_user_ids))

            for round_entity in rounds:
                matches = await self._uow.matches.find_by_round(round_entity.id)

                for match in matches:
                    standing_str = None
                    leading_team = None
                    current_hole = None
                    result_dto = None

                    if match.is_finished() and match.result:
                        points = self._scoring_service.calculate_ryder_cup_points(
                            match.result, match.status.value
                        )
                        total_a_points += points["team_a"]
                        total_b_points += points["team_b"]
                        result_dto = DecidedResultDTO(
                            winner=match.result.get("winner", ""),
                            score=match.result.get("score", ""),
                        )
                    elif match.status.can_record_scores():
                        # In progress: compute standing from hole scores
                        hole_scores = await self._uow.hole_scores.find_by_match(match.id)
                        if hole_scores:
                            match_format = round_entity.match_format
                            hole_results = self._compute_hole_results(
                                hole_scores, match_format
                            )
                            if hole_results:
                                standing = self._scoring_service.calculate_match_standing(
                                    hole_results
                                )
                                standing_str = standing["status"]
                                leading_team = standing["leading_team"]
                                current_hole = standing["holes_played"]

                    team_a_players = [
                        LeaderboardPlayerDTO(
                            user_id=str(p.user_id),
                            user_name=user_names.get(p.user_id, ""),
                        )
                        for p in match.team_a_players
                    ]
                    team_b_players = [
                        LeaderboardPlayerDTO(
                            user_id=str(p.user_id),
                            user_name=user_names.get(p.user_id, ""),
                        )
                        for p in match.team_b_players
                    ]

                    matches_dto.append(
                        LeaderboardMatchDTO(
                            match_id=str(match.id),
                            match_number=match.match_number,
                            match_format=round_entity.match_format.value if round_entity.match_format else "",
                            status=match.status.value,
                            current_hole=current_hole,
                            standing=standing_str,
                            leading_team=leading_team,
                            team_a_players=team_a_players,
                            team_b_players=team_b_players,
                            result=result_dto,
                        )
                    )

            team_a_name = competition.team_a_name if hasattr(competition, "team_a_name") else "Team A"
            team_b_name = competition.team_b_name if hasattr(competition, "team_b_name") else "Team B"

        return LeaderboardResponseDTO(
            competition_id=str(competition.id),
            competition_name=competition.name.value if hasattr(competition.name, "value") else str(competition.name),
            team_a_name=team_a_name,
            team_b_name=team_b_name,
            team_a_points=total_a_points,
            team_b_points=total_b_points,
            matches=matches_dto,
        )

    def _compute_hole_results(self, hole_scores, match_format):
        """Computa resultados por hoyo."""
        scores_by_hole: dict[int, list] = {}
        for hs in hole_scores:
            scores_by_hole.setdefault(hs.hole_number, []).append(hs)

        hole_results = []
        for hole_num in sorted(scores_by_hole.keys()):
            hole_hs = scores_by_hole[hole_num]
            has_validated = any(
                hs.validation_status == ValidationStatus.MATCH for hs in hole_hs
            )
            if not has_validated:
                continue

            team_a_nets = [hs.net_score for hs in hole_hs if hs.team == "A"]
            team_b_nets = [hs.net_score for hs in hole_hs if hs.team == "B"]

            if team_a_nets and team_b_nets:
                winner = self._scoring_service.calculate_hole_winner(
                    team_a_nets, team_b_nets, match_format
                )
                hole_results.append(winner)

        return hole_results

    async def _resolve_user_names(self, user_ids: list[UserId]) -> dict[UserId, str]:
        """Resuelve user_id → 'first_name last_name'."""
        names = {}
        for uid in user_ids:
            user = await self._user_repo.find_by_id(uid)
            if user:
                names[uid] = f"{user.first_name} {user.last_name}"
            else:
                names[uid] = ""
        return names
