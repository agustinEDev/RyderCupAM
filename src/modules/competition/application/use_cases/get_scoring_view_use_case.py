"""Caso de Uso: Obtener vista de scoring de un partido."""

from src.modules.competition.application.dto.scoring_dto import (
    DecidedResultDTO,
    HoleInfoDTO,
    HoleResultDTO,
    HoleScoreEntryDTO,
    MarkerAssignmentResponseDTO,
    MatchStandingDTO,
    PlayerHoleScoreDTO,
    RoundInfoDTO,
    ScoringPlayerDTO,
    ScoringViewResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    MatchNotFoundError,
    RoundNotFoundError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.validation_status import (
    ValidationStatus,
)
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GetScoringViewUseCase:
    """Obtiene la vista completa de scoring para un partido."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repo: UserRepositoryInterface,
        scoring_service: ScoringService,
        golf_course_repo: IGolfCourseRepository | None = None,
    ):
        self._uow = uow
        self._user_repo = user_repo
        self._scoring_service = scoring_service
        self._gc_repo = golf_course_repo

    async def execute(self, match_id_str: str) -> ScoringViewResponseDTO:
        async with self._uow:
            match_id = MatchId(match_id_str)
            match = await self._uow.matches.find_by_id(match_id)
            if not match:
                raise MatchNotFoundError(f"No existe partido con ID {match_id_str}")

            round_entity = await self._uow.rounds.find_by_id(match.round_id)
            if not round_entity:
                raise RoundNotFoundError("La ronda asociada no existe")

            competition = await self._uow.competitions.find_by_id(round_entity.competition_id)
            if not competition:
                raise CompetitionNotFoundError("La competicion asociada no existe")

            hole_scores = await self._uow.hole_scores.find_by_match(match_id)
            user_names = await self._resolve_user_names(match.get_all_player_ids())

            # Cargar golf course para obtener holes y nombre
            golf_course_name = ""
            holes_dto: list[HoleInfoDTO] = []
            if self._gc_repo:
                golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
                if golf_course:
                    golf_course_name = golf_course.name
                    holes_dto = [
                        HoleInfoDTO(
                            hole_number=h.number,
                            par=h.par,
                            stroke_index=h.stroke_index,
                        )
                        for h in sorted(golf_course.holes, key=lambda h: h.number)
                    ]

            round_info = RoundInfoDTO(
                id=str(round_entity.id),
                date=str(round_entity.round_date) if round_entity.round_date else "",
                session_type=round_entity.session_type.value if round_entity.session_type else "",
                golf_course_name=golf_course_name,
            )

            marker_assignments_dto = self._build_marker_assignments(match, user_names)
            players_dto = self._build_players(match, user_names)
            scores_dto, hole_results_list = self._build_scores(hole_scores, round_entity)

            standing = self._scoring_service.calculate_match_standing(hole_results_list)
            decided_result = DecidedResultDTO(**match.decided_result) if match.decided_result else None
            team_a_name = competition.team_1_name if hasattr(competition, "team_1_name") else "Team A"
            team_b_name = competition.team_2_name if hasattr(competition, "team_2_name") else "Team B"

            return ScoringViewResponseDTO(
                match_id=str(match.id),
                match_number=match.match_number,
                match_format=round_entity.match_format.value if round_entity.match_format else "",
                match_status=match.status.value,
                is_decided=match.is_decided,
                decided_result=decided_result,
                round_info=round_info,
                competition_id=str(competition.id),
                team_a_name=team_a_name,
                team_b_name=team_b_name,
                marker_assignments=marker_assignments_dto,
                players=players_dto,
                holes=holes_dto,
                scores=scores_dto,
                match_standing=MatchStandingDTO(**standing),
                scorecard_submitted_by=[str(uid) for uid in match.scorecard_submitted_by],
            )

    def _build_marker_assignments(self, match, user_names):
        """Construye DTOs de marker assignments."""
        return [
            MarkerAssignmentResponseDTO(
                scorer_user_id=str(ma.scorer_user_id),
                scorer_name=user_names.get(ma.scorer_user_id, ""),
                marks_user_id=str(ma.marks_user_id),
                marks_name=user_names.get(ma.marks_user_id, ""),
                marked_by_user_id=str(ma.marked_by_user_id),
                marked_by_name=user_names.get(ma.marked_by_user_id, ""),
            )
            for ma in match.marker_assignments
        ]

    def _build_players(self, match, user_names):
        """Construye DTOs de jugadores."""
        return [
            ScoringPlayerDTO(
                user_id=str(p.user_id),
                user_name=user_names.get(p.user_id, ""),
                team=match.get_player_team(p.user_id) or "",
                tee_category=p.tee_category.value,
                playing_handicap=p.playing_handicap,
                strokes_received=list(p.strokes_received),
            )
            for p in (*match.team_a_players, *match.team_b_players)
        ]

    def _build_scores(self, hole_scores, round_entity):
        """Construye DTOs de scores por hoyo y calcula resultados."""
        scores_by_hole: dict[int, list] = {}
        for hs in hole_scores:
            scores_by_hole.setdefault(hs.hole_number, []).append(hs)

        hole_results_list = []
        scores_dto = []
        match_format = round_entity.match_format

        for hole_num in sorted(scores_by_hole.keys()):
            hole_hs_list = scores_by_hole[hole_num]
            player_scores, team_a_nets, team_b_nets = self._build_hole_player_scores(hole_hs_list)

            hole_result = self._compute_hole_result(
                hole_hs_list, team_a_nets, team_b_nets, match_format, hole_results_list
            )

            scores_dto.append(
                HoleScoreEntryDTO(
                    hole_number=hole_num,
                    player_scores=player_scores,
                    hole_result=hole_result,
                )
            )

        return scores_dto, hole_results_list

    def _build_hole_player_scores(self, hole_hs_list):
        """Construye player scores y clasifica nets por equipo."""
        player_scores = []
        team_a_nets = []
        team_b_nets = []

        for hs in hole_hs_list:
            player_scores.append(
                PlayerHoleScoreDTO(
                    user_id=str(hs.player_user_id),
                    own_score=hs.own_score,
                    marker_score=hs.marker_score,
                    validation_status=hs.validation_status.value.lower(),
                    net_score=hs.net_score,
                    strokes_received_this_hole=hs.strokes_received,
                )
            )
            if hs.net_score is not None:
                if hs.team == "A":
                    team_a_nets.append(hs.net_score)
                else:
                    team_b_nets.append(hs.net_score)

        return player_scores, team_a_nets, team_b_nets

    def _compute_hole_result(self, hole_hs_list, team_a_nets, team_b_nets, match_format, hole_results_list):
        """Calcula el resultado de un hoyo si hay scores validados."""
        has_validated = any(hs.validation_status == ValidationStatus.MATCH for hs in hole_hs_list)
        if not has_validated or not team_a_nets or not team_b_nets:
            return None

        winner = self._scoring_service.calculate_hole_winner(team_a_nets, team_b_nets, match_format)
        hole_results_list.append(winner)
        standing = self._scoring_service.calculate_match_standing(hole_results_list)
        return HoleResultDTO(
            winner=winner,
            standing=standing["status"],
            standing_team=standing["leading_team"],
        )

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
