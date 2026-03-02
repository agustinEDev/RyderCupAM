"""Caso de Uso: Entregar tarjeta de scores."""

from src.modules.competition.application.dto.scoring_dto import (
    ScorecardResultDTO,
    ScorecardStatsDTO,
    SubmitScorecardResponseDTO,
)
from src.modules.competition.application.exceptions import (
    MatchNotFoundError,
    MatchNotScoringError,
    NotMatchPlayerError,
    RoundNotFoundError,
    ScorecardAlreadySubmittedError,
    ScorecardNotReadyError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.validation_status import (
    ValidationStatus,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SubmitScorecardUseCase:
    """Registra la entrega de tarjeta de un jugador."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        scoring_service: ScoringService,
    ):
        self._uow = uow
        self._scoring_service = scoring_service

    async def execute(
        self,
        match_id_str: str,
        user_id: UserId,
    ) -> SubmitScorecardResponseDTO:
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

            if match.has_submitted_scorecard(user_id):
                raise ScorecardAlreadySubmittedError("Ya entregaste tu tarjeta")

            # Validate all played holes have MATCH status
            player_scores = await self._uow.hole_scores.find_by_match_and_player(
                match_id, user_id
            )
            unvalidated = [
                hs
                for hs in player_scores
                if hs.own_submitted and hs.validation_status != ValidationStatus.MATCH
            ]
            if unvalidated:
                holes = [hs.hole_number for hs in unvalidated]
                raise ScorecardNotReadyError(
                    f"Hoyos sin validar: {holes}. Todos los hoyos jugados deben tener validation_status MATCH."
                )

            # Submit scorecard
            match.submit_scorecard(user_id)

            match_complete = False
            result_data = {"winner": None, "score": None}
            points = {"team_a": 0.0, "team_b": 0.0}

            # Load all match scores and round for hole results calculation
            all_scores = await self._uow.hole_scores.find_by_match(match_id)
            round_entity = await self._uow.rounds.find_by_id(match.round_id)
            if not round_entity:
                raise RoundNotFoundError(f"Round not found for match {match_id_str}")
            match_format = round_entity.match_format
            hole_results = self._compute_hole_results(all_scores, match_format)

            # Check if all scorecards submitted
            if match.all_scorecards_submitted():
                match_complete = True
                # Preserve decided result (e.g. "5&4") instead of recalculating
                # from all 18 holes which would give "5UP" (holes_remaining=0)
                if match.is_decided and match.decided_result:
                    result_data = match.decided_result
                else:
                    result_data = self._scoring_service.format_decided_result(hole_results)
                match.complete(result_data)
                points = self._scoring_service.calculate_ryder_cup_points(
                    result_data, match.status.value
                )

                # Auto-complete round
                all_matches = await self._uow.matches.find_by_round(match.round_id)
                all_finished = all(m.is_finished() for m in all_matches)
                if all_finished and round_entity.status == RoundStatus.IN_PROGRESS:
                    round_entity.complete()
                    await self._uow.rounds.update(round_entity)

            await self._uow.matches.update(match)

        # Calculate player stats using hole results
        player_team = match.get_player_team(user_id) or "A"
        stats = self._calculate_player_stats(player_scores, player_team, hole_results)

        return SubmitScorecardResponseDTO(
            match_id=str(match.id),
            submitted_by=str(user_id),
            result=ScorecardResultDTO(
                winner=result_data.get("winner"),
                score=result_data.get("score"),
                team_a_points=points["team_a"],
                team_b_points=points["team_b"],
            ),
            stats=stats,
            match_complete=match_complete,
        )

    def _compute_hole_results(self, all_scores, match_format):
        """Computa resultados por hoyo."""
        scores_by_hole: dict[int, list] = {}
        for hs in all_scores:
            scores_by_hole.setdefault(hs.hole_number, []).append(hs)

        hole_results = []
        for hole_num in sorted(scores_by_hole.keys()):
            hole_hs = scores_by_hole[hole_num]
            has_validated = any(
                hs.validation_status == ValidationStatus.MATCH for hs in hole_hs
            )
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

    def _calculate_player_stats(self, player_scores, player_team, hole_results):
        """Calcula estadisticas del jugador."""
        gross_total = 0
        net_total = 0
        has_gross = False

        for hs in player_scores:
            if hs.own_score is not None and hs.validation_status == ValidationStatus.MATCH:
                gross_total += hs.own_score
                has_gross = True
            if hs.net_score is not None:
                net_total += hs.net_score

        # Count hole results from the player's team perspective
        holes_won = 0
        holes_lost = 0
        holes_halved = 0
        for result in hole_results:
            if result == "HALVED":
                holes_halved += 1
            elif result == player_team:
                holes_won += 1
            else:
                holes_lost += 1

        return ScorecardStatsDTO(
            player_gross_total=gross_total if has_gross else None,
            player_net_total=net_total if has_gross else None,
            holes_won=holes_won,
            holes_lost=holes_lost,
            holes_halved=holes_halved,
        )
