"""Adaptador: el historial de campos sale de las partidas rapidas y los torneos."""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.social.application.exclusive_achievements import round_instant, utc_naive
from src.modules.social.application.ports.player_course_history_interface import (
    CourseRound,
    PlayerCourseHistoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Cuantas vueltas del jugador se miran hacia atras. Quien tenga mas historia que
# esto ya no estrena nada que merezca contarse.
MAX_HISTORY_LOOKUP = 200


class PlayerCourseHistoryAdapter(PlayerCourseHistoryInterface):
    """
    Junta las fuentes de vueltas para decidir si un campo es nuevo: partidas
    rapidas, partidos de la Ryder y grupos de stroke play de torneo (L9).

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

    async def first_round_on_course(
        self, user_id: UserId, golf_course_id: str, timezone: str | None
    ) -> CourseRound | None:
        vueltas = [
            *await self._partidas_rapidas(user_id, golf_course_id),
            *await self._de_torneos_cerrados(user_id, golf_course_id, timezone),
        ]
        return min(vueltas, key=lambda v: v.key, default=None)

    async def _partidas_rapidas(self, user_id: UserId, golf_course_id: str) -> list[CourseRound]:
        """Las partidas rapidas terminadas en el campo, por su instante de creacion."""
        async with self._quick_match_uow:
            partidas = await self._quick_match_uow.quick_matches.list_for_user(
                user_id, status=QuickMatchStatus.COMPLETED, limit=MAX_HISTORY_LOOKUP
            )
        return [
            CourseRound(instant=utc_naive(partida.created_at), source_id=str(partida.id.value))
            for partida in partidas
            if str(partida.golf_course_id.value) == golf_course_id
        ]

    async def _de_torneos_cerrados(
        self, user_id: UserId, golf_course_id: str, timezone: str | None
    ) -> list[CourseRound]:
        """
        Los partidos de la Ryder y los grupos de stroke play en el campo, de
        torneos YA CERRADOS. En el grupo, quien no se presento no piso el
        campo; quien se retiro, si.

        Todo por lotes: partidos, grupos, rondas y torneos, una lectura de cada.
        """
        async with self._competition_uow:
            uow = self._competition_uow
            origenes = [
                (partido.round_id, str(partido.id.value))
                for partido in await uow.matches.find_completed_for_player(
                    user_id, limit=MAX_HISTORY_LOOKUP
                )
            ] + [
                (grupo.round_id, str(grupo.id.value))
                for grupo in await uow.partidas.completadas_de_jugadores([user_id])
                if grupo.estados_de_tarjeta.get(user_id) != EstadoDeTarjeta.NO_PRESENTADO
            ]
            if not origenes:
                return []
            rondas = {
                ronda.id: ronda
                for ronda in await uow.rounds.find_by_ids(list({r for r, _ in origenes}))
                if str(ronda.golf_course_id.value) == golf_course_id
            }
            if not rondas:
                return []
            cerrados = {
                torneo.id
                for torneo in await uow.competitions.find_by_ids(
                    list({r.competition_id for r in rondas.values()})
                )
                if torneo.status == CompetitionStatus.COMPLETED
            }
        return [
            CourseRound(
                instant=round_instant(ronda.round_date, ronda.session_type, timezone),
                source_id=source_id,
                competition_id=str(ronda.competition_id.value),
            )
            for round_id, source_id in origenes
            if (ronda := rondas.get(round_id)) is not None and ronda.competition_id in cerrados
        ]
