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
    PlayerWithdrawnError,
    RoundNotFoundError,
    ScorecardAlreadySubmittedError,
    ScorecardNotReadyError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.validation_status import (
    ValidationStatus,
)
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.stroke_play_scoring import StrokePlayScoring


class SubmitScorecardUseCase:
    """Registra la entrega de tarjeta de un jugador."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        scoring_service: ScoringService,
        actividad: CompetitionActivityPublisherInterface | None = None,
        golf_course_repo: IGolfCourseRepository | None = None,
    ):
        self._uow = uow
        self._scoring_service = scoring_service
        # El par de cada hoyo, para sumar la raya; sin él, la raya no suma
        self._gc_repo = golf_course_repo
        # Los avisos de Actividad (BE-2); sin el, no se avisa
        self._actividad = AvisosDeActividad(actividad)

    @staticmethod
    def _puede_entregar(match, user_id: UserId) -> None:
        """Juega el partido y no esta retirado: el retirado no entrega (W12, W19)."""
        if match.find_player(user_id) is None:
            raise NotMatchPlayerError("No eres jugador de este partido")
        if user_id in match.withdrawn_player_ids:
            raise PlayerWithdrawnError()

    async def execute(
        self,
        match_id_str: str,
        user_id: UserId,
    ) -> SubmitScorecardResponseDTO:
        async with self._uow:
            match_id = MatchId(match_id_str)
            # Con la fila bloqueada: un solo toque mandaba dos envíos a la vez
            # y los dos pasaban la comprobación de «ya la entregaste» (BE #377)
            match = await self._uow.matches.find_by_id_for_update(match_id)
            if not match:
                raise MatchNotFoundError(f"No existe partido con ID {match_id_str}")

            if not match.status.can_record_scores():
                raise MatchNotScoringError(
                    f"Partido no esta en estado para scoring. Estado: {match.status.value}"
                )

            self._puede_entregar(match, user_id)

            # El formato decide de quién es la tarjeta: en foursomes, del bando
            round_entity = await self._uow.rounds.find_by_id(match.round_id)
            if not round_entity:
                raise RoundNotFoundError(f"Round not found for match {match_id_str}")
            match_format = round_entity.match_format

            player_scores = await self._uow.hole_scores.find_by_match_and_player(match_id, user_id)
            ya_entregada = match.has_submitted_scorecard(user_id, match_format)
            # Un partido con todas las tarjetas y todavía abierto se cierra en vez
            # de rechazarse: con la regla de antes cada uno entregaba la suya, y un
            # foursomes a medias al desplegar ya está completo por la de ahora.
            # Sin esto, nadie podría cerrarlo (revisión de la BE #377)
            if ya_entregada and not match.all_scorecards_submitted(match_format):
                if user_id in match.scorecard_submitted_by:
                    raise ScorecardAlreadySubmittedError("Ya entregaste tu tarjeta")
                raise ScorecardAlreadySubmittedError(
                    "Tu compañero ya entregó la tarjeta de vuestra pareja"
                )

            if not ya_entregada:
                self._comprueba_que_todo_esta_validado(player_scores)
                match.submit_scorecard(user_id, match_format)

            match_complete = False
            points = {"team_a": 0.0, "team_b": 0.0}
            competition = None

            # Load all match scores and round for hole results calculation
            all_scores = await self._uow.hole_scores.find_by_match(match_id)
            results_by_hole = self._scoring_service.hole_results_by_hole(
                all_scores, match_format, match.bolas_fuera
            )
            hole_results = list(results_by_hole.values())

            # Result is derived from whichever holes are already validated, so the
            # submitting player sees the real outcome even before every other player
            # has formally submitted their own scorecard.
            # Preserve a decided result (e.g. "5&4") instead of recalculating from
            # all 18 holes, which would give "5UP" (holes_remaining=0).
            if match.is_decided and match.decided_result:
                result_data = match.decided_result
            elif hole_results:
                result_data = self._scoring_service.result_in_hole_order(results_by_hole)
            else:
                result_data = {"winner": None, "score": None}

            # Check if all scorecards submitted
            if match.all_scorecards_submitted(match_format):
                match_complete = True
                match.complete(result_data)
                points = self._scoring_service.calculate_ryder_cup_points(
                    result_data, match.status.value
                )

                # La competicion, para avisar del resultado en Actividad (BE-2)
                competition = await self._uow.competitions.find_by_id(round_entity.competition_id)

                # Auto-complete round
                all_matches = await self._uow.matches.find_by_round(match.round_id)
                all_finished = all(m.is_finished() for m in all_matches)
                if all_finished and round_entity.status == RoundStatus.IN_PROGRESS:
                    round_entity.complete()
                    await self._uow.rounds.update(round_entity)

            await self._uow.matches.update(match)

        await self._avisar_del_resultado(competition, round_entity, match)

        # Calculate player stats using hole results
        player_team = match.get_player_team(user_id) or "A"
        pars = await self._pars_del_jugador(round_entity, match.find_player(user_id))
        stats = self._calculate_player_stats(player_scores, player_team, hole_results, pars)

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

    async def _avisar_del_resultado(self, competition, round_entity, match) -> None:
        """
        Con la ultima tarjeta el partido queda cerrado: a cada jugador, su
        resultado en Actividad, ya guardado (BE-2). Solo se lee la competicion
        al cerrarlo, asi que sin ella no hay nada que contar.
        """
        if competition is not None:
            await self._actividad.match_finished(competition, round_entity, match)

    @staticmethod
    def _comprueba_que_todo_esta_validado(player_scores) -> None:
        """Todos los hoyos jugados tienen que estar validados (MATCH)."""
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

    async def _pars_del_jugador(self, round_entity, player) -> dict[int, int]:
        """El par de cada hoyo en la barra del jugador, o vacío si no se sabe."""
        if self._gc_repo is None or player is None:
            return {}
        course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
        if course is None:
            return {}
        return {
            hole.number: hole.par
            for hole in course.hole_card_for(player.tee_color, player.tee_gender)
        }

    def _calculate_player_stats(self, player_scores, player_team, hole_results, pars=None):
        """
        Calcula estadisticas del jugador.

        La raya validada (los dos sin número) suma su doble bogey neto, `par +
        2 + golpes recibidos` en el partido, y `par + 2` en neto (Agustin, 23
        oct 2026). Sin el par del hoyo no hay con qué contarla y se deja fuera.
        """
        pars = pars or {}
        gross_total = 0
        net_total = 0
        has_gross = False

        for hs in player_scores:
            validado = hs.validation_status == ValidationStatus.MATCH
            if hs.own_score is not None and validado:
                gross_total += hs.own_score
                has_gross = True
            elif validado and hs.own_submitted and hs.hole_number in pars:
                par = pars[hs.hole_number]
                gross_total += StrokePlayScoring.net_double_bogey(par, hs.strokes_received)
                net_total += StrokePlayScoring.net_double_bogey(par, 0)
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
