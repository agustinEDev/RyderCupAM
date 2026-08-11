"""Adaptador: el historial de campos sale de las partidas rapidas y los torneos."""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Cuantas vueltas del jugador se miran hacia atras. Quien tenga mas historia que
# esto ya no estrena nada que merezca contarse.
MAX_HISTORY_LOOKUP = 200


class PlayerCourseHistoryAdapter(PlayerCourseHistoryInterface):
    """
    Junta las dos fuentes de vueltas para decidir si un campo es nuevo.

    Un campo se estrena una sola vez en la vida del jugador, y da igual si fue
    jugando con amigos o en un torneo. Preguntar solo a las partidas rapidas
    haria que un campo estrenado en competicion volviera a anunciarse.
    """

    def __init__(
        self,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        competition_uow: CompetitionUnitOfWorkInterface,
    ):
        self._quick_match_uow = quick_match_uow
        self._competition_uow = competition_uow

    async def has_played_course_before(
        self, user_id: UserId, golf_course_id: str, excluding_match_id: str
    ) -> bool:
        if await self._jugo_en_partida_rapida(user_id, golf_course_id, excluding_match_id):
            return True
        return await self._jugo_en_torneo(user_id, golf_course_id, excluding_match_id)

    async def _jugo_en_partida_rapida(
        self, user_id: UserId, golf_course_id: str, excluding_match_id: str
    ) -> bool:
        async with self._quick_match_uow:
            partidas = await self._quick_match_uow.quick_matches.list_for_user(
                user_id, status=QuickMatchStatus.COMPLETED, limit=MAX_HISTORY_LOOKUP
            )
        return any(
            str(partida.id.value) != excluding_match_id
            and str(partida.golf_course_id.value) == golf_course_id
            for partida in partidas
        )

    async def _jugo_en_torneo(
        self, user_id: UserId, golf_course_id: str, excluding_match_id: str
    ) -> bool:
        async with self._competition_uow:
            partidos = await self._competition_uow.matches.find_completed_for_player(
                user_id, limit=MAX_HISTORY_LOOKUP
            )
            rondas: dict = {}
            for partido in partidos:
                if str(partido.id.value) == excluding_match_id:
                    continue
                if partido.round_id not in rondas:
                    rondas[partido.round_id] = await self._competition_uow.rounds.find_by_id(
                        partido.round_id
                    )
                ronda = rondas[partido.round_id]
                if ronda is not None and str(ronda.golf_course_id.value) == golf_course_id:
                    return True
        return False
