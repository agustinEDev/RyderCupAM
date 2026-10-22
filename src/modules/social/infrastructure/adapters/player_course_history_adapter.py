"""Adaptador: el historial de campos sale de las partidas rapidas y los torneos."""

from datetime import UTC, datetime

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_opening_service import (
    OPENING_HOUR_BY_SESSION,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.social.application.ports.player_course_history_interface import (
    PlayedBefore,
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

    async def has_played_course_before(
        self,
        user_id: UserId,
        golf_course_id: str,
        excluding_match_id: str,
        excluding_competition_id: str | None = None,
        before: PlayedBefore | None = None,
    ) -> bool:
        if await self._jugo_en_partida_rapida(user_id, golf_course_id, excluding_match_id, before):
            return True
        return await self._jugo_en_torneo_cerrado(
            user_id, golf_course_id, excluding_match_id, excluding_competition_id, before
        )

    async def _jugo_en_partida_rapida(
        self,
        user_id: UserId,
        golf_course_id: str,
        excluding_match_id: str,
        before: PlayedBefore | None,
    ) -> bool:
        async with self._quick_match_uow:
            partidas = await self._quick_match_uow.quick_matches.list_for_user(
                user_id, status=QuickMatchStatus.COMPLETED, limit=MAX_HISTORY_LOOKUP
            )
        return any(
            str(partida.id.value) != excluding_match_id
            and str(partida.golf_course_id.value) == golf_course_id
            and (before is None or _rapida_antes(partida.created_at, before))
            for partida in partidas
        )

    async def _jugo_en_torneo_cerrado(
        self,
        user_id: UserId,
        golf_course_id: str,
        excluding_match_id: str,
        excluding_competition_id: str | None,
        before: PlayedBefore | None,
    ) -> bool:
        """
        Un partido de la Ryder o un grupo de stroke play en ese campo, de un
        torneo YA CERRADO que no sea el que se juzga: un torneo en juego o
        cancelado todavia no se ha jugado (revision del 22 oct 2026). En el
        grupo, quien no se presento no piso el campo; quien se retiro, si.

        Todo por lotes: partidos, grupos, rondas y torneos, una lectura de cada.
        """
        async with self._competition_uow:
            uow = self._competition_uow
            partidos = [
                partido
                for partido in await uow.matches.find_completed_for_player(
                    user_id, limit=MAX_HISTORY_LOOKUP
                )
                if str(partido.id.value) != excluding_match_id
            ]
            grupos = [
                grupo
                for grupo in await uow.partidas.completadas_de_jugadores([user_id])
                if str(grupo.id.value) != excluding_match_id
                and grupo.estados_de_tarjeta.get(user_id) != EstadoDeTarjeta.NO_PRESENTADO
            ]
            round_ids = {p.round_id for p in partidos} | {g.round_id for g in grupos}
            if not round_ids:
                return False
            rondas = await uow.rounds.find_by_ids(list(round_ids))
            en_el_campo = [
                r
                for r in rondas
                if str(r.golf_course_id.value) == golf_course_id
                and (before is None or _ronda_antes(r, before))
            ]
            if not en_el_campo:
                return False
            torneos = await uow.competitions.find_by_ids(
                list({r.competition_id for r in en_el_campo})
            )
        return any(
            torneo.status == CompetitionStatus.COMPLETED
            and str(torneo.id.value) != excluding_competition_id
            for torneo in torneos
        )


def _rapida_antes(creada: datetime, before: PlayedBefore) -> bool:
    """
    Si una partida rapida se jugo ANTES del corte. No guarda cuando se jugo,
    solo cuando se creo, y se juega del tiron: ese instante vale. Con el
    instante del corte (el campo tiene zona) se compara en UTC; sin el, por
    fecha, y el mismo dia no cuenta.
    """
    if before.utc_instant is None:
        return creada.date() < before.day
    return _utc_sin_zona(creada) < before.utc_instant


def _ronda_antes(ronda, before: PlayedBefore) -> bool:
    """
    Si una ronda de otro torneo EN EL MISMO CAMPO se jugo antes del corte: misma
    zona, asi que basta la fecha y la hora local de su sesion. Sin la hora del
    corte, por fecha: el mismo dia no cuenta.
    """
    hora = OPENING_HOUR_BY_SESSION.get(ronda.session_type)
    if before.local_hour is None or hora is None:
        return ronda.round_date < before.day
    return (ronda.round_date, hora) < (before.day, before.local_hour)


def _utc_sin_zona(instante: datetime) -> datetime:
    """En UTC y sin zona, como `shared_games_adapter`: las fechas sin zona ya son UTC."""
    if instante.tzinfo is None:
        return instante
    return instante.astimezone(UTC).replace(tzinfo=None)
