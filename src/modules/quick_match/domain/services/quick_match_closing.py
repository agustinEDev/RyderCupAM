"""
Cuándo se cierra sola una partida rápida que nadie termina (Agustín, 23 oct 2026).

Los jugadores olvidan finalizarla, y una partida abierta para siempre no
publica su resultado ni cuenta para nada. Se cierra:

- **En juego**: al acabar el día siguiente al que empezó, en la hora del campo,
  como los partidos de competición. El día de margen es para los golpes
  anotados sin cobertura, que pueden llegar al día siguiente. El plazo es fijo:
  un golpe tarde no lo aplaza.
- **Sin empezar (PENDING)**: a los 7 días de crearse. Se crean con días de
  antelación —el viernes para el domingo—, y el día siguiente las cancelaría
  antes de jugarlas.

Lo que se cierra más de 2 días después de su plazo no se publica en Actividad:
saldría como nueva una partida de hace semanas.

Las fechas son UTC sin zona, como las que se guardan: `created_at` y
`started_at` salen de `datetime.now()` en un servidor en UTC (Render y el Kind).
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..value_objects.quick_match_status import QuickMatchStatus

PENDING_LIFETIME = timedelta(days=7)
DAYS_TO_FINISH = 2
LATE_PUBLISHING_LIMIT = timedelta(days=2)


def closes_at(
    *,
    status: QuickMatchStatus,
    created_at: datetime,
    started_at: datetime | None,
    timezone: str | None,
) -> datetime | None:
    """El instante (UTC sin zona) en que se cierra, o None si ya está cerrada."""
    if status == QuickMatchStatus.PENDING:
        return created_at + PENDING_LIFETIME
    if status != QuickMatchStatus.IN_PROGRESS:
        return None

    # Las de antes no guardan cuándo empezaron: se crean y empiezan el mismo día
    inicio = started_at or created_at
    zona = _zona(timezone)
    dia = inicio.replace(tzinfo=UTC).astimezone(zona).date()
    cierre = datetime.combine(dia + timedelta(days=DAYS_TO_FINISH), time(0), tzinfo=zona)
    return cierre.astimezone(UTC).replace(tzinfo=None)


def _zona(timezone: str | None):
    """
    La zona del campo, o UTC si no se sabe o no existe: el campo leído de la BD
    no pasa por su validación, y una zona rara no puede tumbar el cierre.
    """
    if not timezone:
        return UTC
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def publishes_when_closed(closing: datetime, now: datetime) -> bool:
    """Si al cerrarla ahora se publica en Actividad: no si va más de 2 días tarde."""
    return now - closing <= LATE_PUBLISHING_LIMIT
