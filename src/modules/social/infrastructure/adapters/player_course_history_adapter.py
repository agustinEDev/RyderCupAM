"""Adaptador: el historial de campos sale de las partidas rapidas y los torneos."""

from collections.abc import Collection

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.social.application.exclusive_achievements import (
    PlayedRound,
    round_instant,
    utc_naive,
)
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class PlayerCourseHistoryAdapter(PlayerCourseHistoryInterface):
    """
    Junta las fuentes de vueltas: partidas rapidas, partidos de la Ryder y
    grupos de stroke play de torneo (L9).

    Un campo se estrena una sola vez en la vida del jugador, y da igual si fue
    jugando con amigos o en un torneo. Preguntar solo a las partidas rapidas
    haria que un campo estrenado en competicion volviera a anunciarse.
    """

    def __init__(
        self,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        competition_uow: CompetitionUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
    ):
        self._quick_match_uow = quick_match_uow
        self._competition_uow = competition_uow
        self._golf_course_uow = golf_course_uow

    async def played_rounds(self, user_ids: Collection[UserId]) -> list[PlayedRound]:
        usuarios = list(set(user_ids))
        if not usuarios:
            return []
        return [
            *await self._partidas_rapidas(usuarios),
            *await self._de_torneos_cerrados(usuarios),
        ]

    async def _partidas_rapidas(self, usuarios: list[UserId]) -> list[PlayedRound]:
        """Las partidas rapidas terminadas con algun hoyo suyo, por cuando se jugaron."""
        async with self._quick_match_uow:
            partidas = await self._quick_match_uow.quick_matches.list_completed_for_users(usuarios)
            hoyos = await self._quick_match_uow.quick_match_hole_scores.played_holes(
                [p.id for p in partidas]
            )
        rondas = []
        for partida in partidas:
            for user_id in usuarios:
                # Un participante con cuenta lleva el id de su usuario
                jugados = hoyos.get((partida.id, ParticipantId(user_id.value)), 0)
                if jugados:
                    rondas.append(
                        PlayedRound(
                            user_id=user_id,
                            golf_course_id=str(partida.golf_course_id.value),
                            instant=utc_naive(partida.played_at),
                            source_id=str(partida.id.value),
                            holes_played=jugados,
                        )
                    )
        return rondas

    async def _de_torneos_cerrados(self, usuarios: list[UserId]) -> list[PlayedRound]:
        """
        Los partidos de la Ryder y los grupos de stroke play terminados, de
        torneos CERRADOS, con algun hoyo suyo. En el grupo, el no presentado
        no piso el campo. Por lotes: una lectura de cada cosa para todos.
        """
        buscados = set(usuarios)
        async with self._competition_uow:
            uow = self._competition_uow
            partidos = await uow.matches.find_finished_for_players(usuarios)
            grupos = await uow.partidas.completadas_de_jugadores(usuarios)
            hoyos_partido = await uow.hole_scores.played_holes([p.id for p in partidos])
            hoyos_grupo = await uow.golpes_de_partida.hoyos_jugados([g.id for g in grupos])

            # (jugador, ronda, origen, tipo, quienes jugaron, hoyos)
            vueltas = []
            for partido in partidos:
                jugadores = [p.user_id for p in (*partido.team_a_players, *partido.team_b_players)]
                for user_id in buscados.intersection(jugadores):
                    jugados = hoyos_partido.get((partido.id, user_id), 0)
                    if jugados:
                        vueltas.append(
                            (
                                user_id,
                                partido.round_id,
                                str(partido.id.value),
                                "MATCH",
                                jugadores,
                                jugados,
                            )
                        )
            for grupo in grupos:
                for user_id in buscados.intersection(grupo.user_ids):
                    if grupo.estados_de_tarjeta.get(user_id) == EstadoDeTarjeta.NO_PRESENTADO:
                        continue
                    jugados = hoyos_grupo.get((grupo.id, user_id), 0)
                    if jugados:
                        vueltas.append(
                            (
                                user_id,
                                grupo.round_id,
                                str(grupo.id.value),
                                "TEE_GROUP",
                                grupo.user_ids,
                                jugados,
                            )
                        )
            if not vueltas:
                return []
            rondas = {
                ronda.id: ronda
                for ronda in await uow.rounds.find_by_ids(list({v[1] for v in vueltas}))
            }
            cerrados = {
                torneo.id
                for torneo in await uow.competitions.find_by_ids(
                    list({r.competition_id for r in rondas.values()})
                )
                if torneo.status == CompetitionStatus.COMPLETED
            }
        async with self._golf_course_uow:
            campos = {
                campo.id: campo
                for campo in await self._golf_course_uow.golf_courses.find_by_ids(
                    list({r.golf_course_id for r in rondas.values()})
                )
            }

        resultado = []
        for user_id, round_id, origen, tipo, jugadores, jugados in vueltas:
            ronda = rondas.get(round_id)
            if ronda is None or ronda.competition_id not in cerrados:
                continue
            campo = campos.get(ronda.golf_course_id)
            resultado.append(
                PlayedRound(
                    user_id=user_id,
                    golf_course_id=str(ronda.golf_course_id.value),
                    instant=round_instant(
                        ronda.round_date, ronda.session_type, campo.timezone if campo else None
                    ),
                    source_id=origen,
                    holes_played=jugados,
                    competition_id=str(ronda.competition_id.value),
                    kind=tipo,
                    player_ids=tuple(sorted({str(u.value) for u in jugadores})),
                    round_date=ronda.round_date,
                )
            )
        return resultado
