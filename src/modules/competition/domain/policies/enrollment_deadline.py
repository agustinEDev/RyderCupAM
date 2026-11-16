"""
Hasta cuándo se apunta uno a una competición (decidido el 15 nov 2026).

Las inscripciones cierran a las **12:00 del día anterior** al torneo, a la hora
del campo donde se juega: el organizador tiene la tarde para montar salidas y
partidos. Vale para la Ryder, el Stableford y el Medal, públicas y privadas.

La zona es la del primer campo, como la de la apertura programada; sin campo
—o con una zona que no existe—, la de Madrid. Aquí no se espera a saberla como
al abrir: abrir a deshora anuncia una cosa y hace otra, pero sin plazo nadie
cerraría nunca.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.modules.competition.domain.policies.zona_horaria import zona_del_campo

# Sin campo todavía: la de casi todos los torneos de hoy
ZONA_SIN_CAMPO = "Europe/Madrid"
HORA_DEL_CIERRE = time(12, 0)


def closes_at(start_date: date, timezone: str | None) -> datetime:
    """
    El instante en que cierran, con la zona del campo.

    Las 12:00 se le PONEN al día con la zona, no se convierten: convertirlas
    las movería a la zona de quien mira.
    """
    zona = zona_del_campo(timezone) or ZoneInfo(ZONA_SIN_CAMPO)
    return datetime.combine(start_date - timedelta(days=1), HORA_DEL_CIERRE, tzinfo=zona)


def en_utc(instante: datetime) -> datetime:
    """Con zona, a UTC; sin ella, se lee en UTC, que es como se guardan."""
    if instante.tzinfo is None:
        return instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC)


def fecha_en_el_campo(now: datetime, timezone: str | None) -> date:
    """
    Qué día es ahora en el campo: la fecha de `now` leída con la zona del campo
    (sin campo, la de Madrid), no la del servidor (F-01).
    """
    zona = zona_del_campo(timezone) or ZoneInfo(ZONA_SIN_CAMPO)
    return en_utc(now).astimezone(zona).date()


def has_passed(start_date: date, timezone: str | None, now: datetime) -> bool:
    """Si ya cerraron: desde las 12:00 en punto."""
    return en_utc(now) >= closes_at(start_date, timezone)
