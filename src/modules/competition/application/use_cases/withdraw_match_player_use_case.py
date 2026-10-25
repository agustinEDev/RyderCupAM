"""Caso de Uso: retirar a un jugador de un fourball, o deshacerlo (25 oct 2026)."""

from src.modules.competition.application.dto.scoring_dto import (
    DecidedResultDTO,
    WithdrawalResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    MatchNotFoundError,
    NotMatchPlayerError,
    RoundNotFoundError,
    WithdrawalNotAllowedError,
)
from src.modules.competition.application.services.decision_del_partido import (
    revisa_la_decision,
)
from src.modules.competition.domain.exceptions.competition_violations import WithdrawalViolation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.user.domain.value_objects.user_id import UserId


class WithdrawMatchPlayerUseCase:
    """
    Retira a un jugador de un fourball de torneo, o lo devuelve al partido.

    Si un jugador no se presenta o se va, con la regla de las cuatro bolas el
    partido no avanzaba nunca (Agustín, 24 oct 2026). Retirado, su bola deja de
    contar en los hoyos que no tenía validados y su bando juega con la de su
    pareja. Pueden hacerlo él mismo, su pareja, el organizador o un admin; los
    rivales no. Las reglas del partido (solo fourball, no el último del bando, sin
    tarjetas entregadas...) son del dominio, `Match.withdraw_player`.
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface, scoring_service: ScoringService):
        self._uow = uow
        self._scoring_service = scoring_service

    async def execute(
        self,
        match_id_str: str,
        actor_id: UserId,
        player_id_str: str,
        *,
        is_admin: bool = False,
        undo: bool = False,
    ) -> WithdrawalResponseDTO:
        async with self._uow:
            match_id = MatchId(match_id_str)
            # Bloqueada: un golpe que llega a la vez recalcula la decisión con
            # los retirados, y tiene que ver los de después de esto
            match = await self._uow.matches.find_by_id_for_update(match_id)
            if not match:
                raise MatchNotFoundError(f"No existe partido con ID {match_id_str}")
            try:
                player_id = UserId(player_id_str)
            except ValueError as e:
                raise NotMatchPlayerError("El jugador no pertenece a este partido") from e

            round_entity = await self._uow.rounds.find_by_id(match.round_id)
            if not round_entity:
                raise RoundNotFoundError("La ronda asociada no existe")
            competition = await self._uow.competitions.find_by_id(round_entity.competition_id)
            if not competition:
                raise CompetitionNotFoundError("La competicion asociada no existe")

            self._autoriza(match, actor_id, player_id, is_admin or competition.is_creator(actor_id))

            try:
                if undo:
                    # Lo cerrado sin su bola se queda asi; vuelve en lo demas
                    filas = await self._uow.hole_scores.find_by_match(match.id)
                    cerrados = self._scoring_service.hoyos_cerrados_sin_su_bola(
                        filas, round_entity.match_format, match.bolas_fuera, player_id
                    )
                    match.reinstate_player(player_id, cerrados)
                else:
                    match.withdraw_player(player_id, round_entity.match_format)
            except WithdrawalViolation as e:
                raise WithdrawalNotAllowedError(e.reason, str(e)) from e

            await revisa_la_decision(
                self._uow, self._scoring_service, match, round_entity.match_format
            )
            await self._uow.matches.update(match)

        return WithdrawalResponseDTO(
            match_id=str(match.id),
            withdrawn_player_ids=[str(uid) for uid in match.withdrawn_player_ids],
            decided_result=DecidedResultDTO(**match.decided_result)
            if match.decided_result
            else None,
        )

    @staticmethod
    def _autoriza(match, actor_id: UserId, player_id: UserId, gestiona: bool) -> None:
        """Él mismo, su pareja, el organizador o un admin (W1)."""
        equipo = match.get_player_team(player_id)
        if equipo is None:
            raise NotMatchPlayerError("El jugador no pertenece a este partido")
        if gestiona:
            return
        if match.get_player_team(actor_id) != equipo:
            raise NotMatchPlayerError("Solo el jugador, su pareja o el organizador")
