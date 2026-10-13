"""
Lo que la tarjeta de «Mis competiciones» necesita y la competición no sabe sola
(FE #846): cuántos días se juega y la próxima salida de quien mira.

Lo terminado se decide por el estado y no por la fecha, para no depender de la
zona del campo. En stroke play, por su partida: la franja no se da por acabada
nunca, cada partida sí. En la Ryder, por el partido; y una sesión aún sin
partidos generados cuenta, sin hora. En una competición terminada o cancelada
no hay próxima salida, quede lo que quede sin cerrar. Y lo de antes de ayer no
cuenta: con un día de margen no hace falta la zona del campo, y lo de hoy no se
pierde nunca (decidido con Agustín el 13 oct 2026).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from src.modules.competition.application.services.envelope_desk import ORDEN_DE_SESION
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidasInvalidaError
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.user.domain.value_objects.user_id import UserId

_EN_JUEGO = {MatchStatus.SCHEDULED, MatchStatus.IN_PROGRESS}
_SIN_PARTIDOS = {RoundStatus.PENDING_TEAMS, RoundStatus.PENDING_MATCHES}


@dataclass(frozen=True)
class ProximaSalida:
    """Cuándo sale: sin hora en la Ryder, o sin partidas generadas todavía."""

    fecha: date
    sesion: SessionType
    hora: time | None


@dataclass(frozen=True)
class Resumen:
    """Días de juego (solo stroke play) y próxima salida (solo quien juega)."""

    jornadas: int | None
    proxima: ProximaSalida | None


class ResumenDeLaCompeticion:
    """Como mucho tres lecturas por competición: sesiones, y sus partidas y plazas."""

    @staticmethod
    async def de(
        competicion: Competition,
        user_id: UserId,
        juega: bool,
        uow: CompetitionUnitOfWorkInterface,
        hoy: date | None = None,
    ) -> Resumen:
        """
        Args:
            juega: Si quien mira está inscrito y aprobado; si no, no tiene salida
            hoy: El día de hoy en UTC (por defecto, el del reloj)
        """
        stroke_play = competicion.stroke_play is not None
        busca_salida = juega and not competicion.status.is_final()
        if not stroke_play and not busca_salida:
            return Resumen(None, None)
        sesiones = await uow.rounds.find_by_competition(competicion.id)
        jornadas = len({s.round_date for s in sesiones}) if stroke_play else None
        if not busca_salida:
            return Resumen(jornadas, None)
        if stroke_play:
            candidatas = await _en_stroke_play(sesiones, competicion, user_id, uow)
        else:
            candidatas = await _en_la_ryder(sesiones, user_id, uow)
        desde = (hoy or datetime.now(UTC).date()) - timedelta(days=1)
        candidatas = [c for c in candidatas if c.fecha >= desde]
        proxima = min(candidatas, key=lambda s: (s.fecha, ORDEN_DE_SESION[s.sesion]), default=None)
        return Resumen(jornadas, proxima)


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
    for plaza in await uow.plazas.del_jugador(competicion.id, user_id):
        franja = franjas.get(plaza.round_id)
        if franja is not None and franja.id not in con_partida:
            salidas.append(ProximaSalida(franja.round_date, franja.session_type, None))
    return salidas


def _hora(franja: Round, numero: int) -> time | None:
    hoja = franja.hoja_de_salidas
    if hoja is None:
        return None
    # Con huecos en la numeración puede no tener salida: lo dice la hoja
    try:
        return hoja.hora_de(numero)
    except HojaDeSalidasInvalidaError:
        return None


async def _en_la_ryder(
    sesiones: Sequence[Round], user_id: UserId, uow: CompetitionUnitOfWorkInterface
) -> list[ProximaSalida]:
    # Lo terminado lo dice el partido: una sesión acabada solo tiene partidos acabados.
    # Con partidos generados, solo cuentan los suyos: en una sesión puede descansar
    por_id = {s.id: s for s in sesiones}
    partidos = await uow.matches.find_by_rounds_for_player(list(por_id), user_id)
    sin_partidos = [
        ProximaSalida(s.round_date, s.session_type, None)
        for s in sesiones
        if s.status in _SIN_PARTIDOS
    ]
    return sin_partidos + [
        ProximaSalida(por_id[p.round_id].round_date, por_id[p.round_id].session_type, None)
        for p in partidos
        if p.status in _EN_JUEGO
    ]
