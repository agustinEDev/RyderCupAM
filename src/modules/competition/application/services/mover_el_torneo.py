"""
Mover un torneo cerrado por el plazo de inscripción (R3, O1, O4; 16 nov 2026).

Se mueve entero: sus sesiones y franjas, con sus horas y sus jugadores, y la
actualización de hándicaps que el organizador dejó programada. Pero solo si no
ha empezado nada: lo decide el RELOJ, no solo el estado de la sesión, porque las
partidas salen por su hora sin que nadie las ponga en juego.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.policies.enrollment_deadline import ZONA_SIN_CAMPO, en_utc
from src.modules.competition.domain.policies.zona_horaria import zona_del_campo
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_opening_service import ScoringOpeningService
from src.modules.competition.domain.value_objects.round_status import RoundStatus


def _zona(nombre: str | None) -> ZoneInfo:
    return zona_del_campo(nombre) or ZoneInfo(ZONA_SIN_CAMPO)


async def alguna_sesion_empezada(
    uow: CompetitionUnitOfWorkInterface,
    rondas: Sequence[Round],
    zonas: ICompetitionTimezone,
    ahora: datetime,
) -> bool:
    """
    Si alguna sesión ya empezó: en juego o terminada, con una partida empezada, o
    porque le llegó su hora —la primera salida de una franja, la apertura de la
    anotación de una sesión de Ryder—, con la zona de su campo (D1).
    """
    instante = en_utc(ahora)
    for ronda in rondas:
        if ronda.status in (RoundStatus.IN_PROGRESS, RoundStatus.COMPLETED):
            return True
        nombre = await zonas.for_course(ronda.golf_course_id)
        hoja = ronda.hoja_de_salidas
        if hoja is not None:
            if any(p.empezada for p in await uow.partidas.de_la_franja(ronda.id)):
                return True
            empieza = datetime.combine(ronda.round_date, hoja.primera_salida, _zona(nombre))
        else:
            abre = ScoringOpeningService.opens_at(
                ronda.round_date, ronda.session_type, nombre or ZONA_SIN_CAMPO
            )
            if abre is None:
                continue
            empieza = abre
        if instante >= empieza:
            return True
    return False


async def mover_la_actualizacion_programada(
    uow: CompetitionUnitOfWorkInterface,
    competition: Competition,
    dias: int,
    zonas: ICompetitionTimezone,
    ahora: datetime,
) -> None:
    """
    La actualización de hándicaps programada, los mismos días y a la misma hora
    del campo, aunque entre medias cambie la hora (O4). Sin programada, nada.
    """
    para = await uow.handicap_updates.programada_de(competition.id)
    if para is None:
        return
    zona = _zona(await zonas.for_competition(competition))
    local = en_utc(para).astimezone(zona)
    # La suma con zona es de reloj de pared: la misma hora de allí, aunque cambie la hora
    movida = (local + timedelta(days=dias)).astimezone(UTC)
    await uow.handicap_updates.programar(
        competition.id, movida if para.tzinfo is not None else movida.replace(tzinfo=None), ahora
    )
