"""Caso de Uso: Registrar score de un hoyo."""

from src.modules.competition.application.dto.scoring_dto import (
    ScoringViewResponseDTO,
    SubmitHoleScoreBodyDTO,
)
from src.modules.competition.application.exceptions import (
    InvalidHoleNumberError,
    MatchNotFoundError,
    MatchNotScoringError,
    NotMatchPlayerError,
    RoundNotFoundError,
)
from src.modules.competition.domain.entities.hole_score import MAX_HOLE, MIN_HOLE
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.validation_status import ValidationStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SubmitHoleScoreUseCase:
    """Registra el score de un jugador en un hoyo especifico."""

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

    async def execute(
        self,
        match_id_str: str,
        hole_number: int,
        body: SubmitHoleScoreBodyDTO,
        user_id: UserId,
    ) -> ScoringViewResponseDTO:
        async with self._uow:
            match_id = MatchId(match_id_str)
            match = await self._uow.matches.find_by_id(match_id)
            if not match:
                raise MatchNotFoundError(f"No existe partido con ID {match_id_str}")

            if not match.status.can_record_scores():
                raise MatchNotScoringError(
                    f"Partido no esta en estado para scoring. Estado: {match.status.value}"
                )

            if match.find_player(user_id) is None:
                raise NotMatchPlayerError("No eres jugador de este partido")

            # Tras entregar tarjeta: own_score ignorado, marker_score sigue editable
            own_score_locked = match.has_submitted_scorecard(user_id)

            marked_player_uid = UserId(body.marked_player_id)
            if match.find_player(marked_player_uid) is None:
                raise NotMatchPlayerError("El jugador marcado no pertenece a este partido")

            # Tarjeta del marcado entregada: marker_score ignorado, own_score sigue editable
            marker_score_locked = match.has_submitted_scorecard(marked_player_uid)

            if not MIN_HOLE <= hole_number <= MAX_HOLE:
                raise InvalidHoleNumberError(f"Hoyo invalido: {hole_number}")

            round_entity = await self._uow.rounds.find_by_id(match.round_id)
            if not round_entity:
                raise RoundNotFoundError("La ronda asociada no existe")
            match_format = round_entity.match_format

            if not own_score_locked:
                await self._update_own_scores(match, match_id, hole_number, body, user_id, match_format)
            if not marker_score_locked:
                await self._update_marker_scores(match, match_id, hole_number, body, marked_player_uid, match_format)
            await self._check_decided(match, match_id, match_format)

        # Return full scoring view
        from src.modules.competition.application.use_cases.get_scoring_view_use_case import (  # noqa: PLC0415
            GetScoringViewUseCase,
        )

        view_uc = GetScoringViewUseCase(self._uow, self._user_repo, self._scoring_service, self._gc_repo)
        return await view_uc.execute(match_id_str)

    async def _update_own_scores(self, match, match_id, hole_number, body, user_id, match_format):
        """Actualiza own_score para los jugadores afectados."""
        affected_own_ids = self._scoring_service.get_affected_player_ids(
            match.team_a_players, match.team_b_players, user_id, match_format
        )
        for pid in affected_own_ids:
            hs = await self._uow.hole_scores.find_one(match_id, hole_number, pid)
            if hs:
                hs.set_own_score(body.own_score)
                hs.recalculate_validation()
                await self._uow.hole_scores.update(hs)

    async def _update_marker_scores(self, match, match_id, hole_number, body, marked_player_id, match_format):
        """Actualiza marker_score para los jugadores marcados afectados."""
        affected_marked_ids = self._scoring_service.get_affected_marked_player_ids(
            match.team_a_players, match.team_b_players, marked_player_id, match_format
        )
        for pid in affected_marked_ids:
            hs = await self._uow.hole_scores.find_one(match_id, hole_number, pid)
            if hs:
                hs.set_marker_score(body.marked_score)
                hs.recalculate_validation()
                await self._uow.hole_scores.update(hs)

    async def _check_decided(self, match, match_id, match_format):
        """Verifica si el partido esta matematicamente decidido."""
        all_scores = await self._uow.hole_scores.find_by_match(match_id)
        hole_results = self._compute_hole_results(all_scores, match_format)
        standing = self._scoring_service.calculate_match_standing(hole_results)
        if self._scoring_service.is_match_decided(standing) and not match.is_decided:
            decided_result = self._scoring_service.format_decided_result(hole_results)
            match.mark_decided(decided_result)
            await self._uow.matches.update(match)

    def _compute_hole_results(self, all_scores, match_format):
        """Computa resultados por hoyo a partir de todos los scores."""
        scores_by_hole: dict[int, list] = {}
        for hs in all_scores:
            scores_by_hole.setdefault(hs.hole_number, []).append(hs)

        hole_results = []
        for hole_num in sorted(scores_by_hole.keys()):
            hole_hs = scores_by_hole[hole_num]
            has_validated = any(hs.validation_status == ValidationStatus.MATCH for hs in hole_hs)
            if not has_validated:
                continue

            team_a_nets = [hs.net_score for hs in hole_hs if hs.team == "A" and hs.net_score is not None]
            team_b_nets = [hs.net_score for hs in hole_hs if hs.team == "B" and hs.net_score is not None]

            if team_a_nets and team_b_nets:
                winner = self._scoring_service.calculate_hole_winner(
                    team_a_nets, team_b_nets, match_format
                )
                hole_results.append(winner)

        return hole_results
