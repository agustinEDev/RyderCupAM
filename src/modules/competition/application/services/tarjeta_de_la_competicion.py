"""
Lo que la tarjeta de «Mis competiciones» necesita y la competición no sabe sola
(FE #846): cuántos días se juega y la próxima salida de quien mira.

Lo terminado se decide por el estado y no por la fecha, para no depender de la
zona del campo. En stroke play, por su partida: la franja no se da por acabada
nunca, cada partida sí. En la Ryder, por el partido.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time

from src.modules.competition.application.services.envelope_desk import ORDEN_DE_SESION
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.user.domain.value_objects.user_id import UserId

_EN_JUEGO = {MatchStatus.SCHEDULED, MatchStatus.IN_PROGRESS}


@dataclass(frozen=True)
class ProximaSalida:
    """Cuándo sale: sin hora en la Ryder, o sin partidas generadas todavía."""

    fecha: date
    sesion: SessionType
    hora: time | None


@dataclass(frozen=True)
class Tarjeta:
    """Días de juego (solo stroke play) y próxima salida (solo quien juega)."""

    jornadas: int | None
    proxima: ProximaSalida | None


class TarjetaDeLaCompeticion:
    """Como mucho tres lecturas por competición: sesiones, y sus partidas y plazas."""

    @staticmethod
    async def de(
        competicion: Competition,
        user_id: UserId,
        juega: bool,
        uow: CompetitionUnitOfWorkInterface,
    ) -> Tarjeta:
        """
        Args:
            juega: Si quien mira está inscrito y aprobado; si no, no tiene salida
        """
        stroke_play = competicion.stroke_play is not None
        if not stroke_play and not juega:
            return Tarjeta(None, None)
        sesiones = await uow.rounds.find_by_competition(competicion.id)
        jornadas = len({s.round_date for s in sesiones}) if stroke_play else None
        if not juega:
            return Tarjeta(jornadas, None)
        if stroke_play:
            candidatas = await _en_stroke_play(sesiones, competicion, user_id, uow)
        else:
            candidatas = await _en_la_ryder(sesiones, user_id, uow)
        proxima = min(candidatas, key=lambda s: (s.fecha, ORDEN_DE_SESION[s.sesion]), default=None)
        return Tarjeta(jornadas, proxima)


async def _en_stroke_play(
    sesiones: Sequence[Round],
    competicion: Competition,
    user_id: UserId,
    uow: CompetitionUnitOfWorkInterface,
) -> list[ProximaSalida]:
    franjas = {s.id: s for s in sesiones if s.hoja_de_salidas is not None}
    partidas = await uow.partidas.del_jugador(competicion.id, user_id)
    salidas = []
    for partida in partidas:
        franja = franjas.get(partida.round_id)
        # Su tarjeta cerrada (entregada, retirado, no presentado): esa ya no la juega.
        # Una partida acabada tiene todas cerradas
        if franja is None or partida.estados_de_tarjeta.get(user_id) != EstadoDeTarjeta.JUGANDO:
            continue
        salidas.append(
            ProximaSalida(franja.round_date, franja.session_type, _hora(franja, partida.numero))
        )
    # Con plaza y sin partida en esa franja: aún no se han generado
    con_partida = {p.round_id for p in partidas}
    for plaza in await uow.plazas.de_la_competicion(competicion.id):
        franja = franjas.get(plaza.round_id)
        if plaza.user_id == user_id and franja is not None and franja.id not in con_partida:
            salidas.append(ProximaSalida(franja.round_date, franja.session_type, None))
    return salidas


def _hora(franja: Round, numero: int) -> time | None:
    hoja = franja.hoja_de_salidas
    # Con huecos en la numeración puede no tener salida en la hoja
    if hoja is None or not 1 <= numero <= hoja.numero_de_salidas:
        return None
    return hoja.hora_de(numero)


async def _en_la_ryder(
    sesiones: Sequence[Round], user_id: UserId, uow: CompetitionUnitOfWorkInterface
) -> list[ProximaSalida]:
    # Lo terminado lo dice el partido: una sesión acabada solo tiene partidos acabados
    por_id = {s.id: s for s in sesiones}
    partidos = await uow.matches.find_by_rounds(list(por_id))
    return [
        ProximaSalida(por_id[p.round_id].round_date, por_id[p.round_id].session_type, None)
        for p in partidos
        if p.status in _EN_JUEGO and p.find_player(user_id) is not None
    ]
