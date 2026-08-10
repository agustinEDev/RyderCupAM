"""
El cursor con el que se pagina el feed.

Vive aparte porque lo comparten el feed de amigos y la actividad de un jugador:
son la misma paginacion sobre los mismos eventos, y dos implementaciones se
separarian en cuanto una de las dos cambiara de formato.

El cursor son **dos** valores, fecha e id, y no solo la fecha. Todos los logros
de una misma vuelta se publican con el mismo `occurred_at` —salen del mismo
instante—, asi que un cursor por fecha sola dejaria fuera los que aun no se han
enseñado de esa vuelta.
"""

from datetime import UTC, datetime
from uuid import UUID

from src.modules.social.domain.entities.activity_event import ActivityEvent

# La fecha en ISO no contiene '|', asi que parte el cursor sin ambiguedad
CURSOR_SEPARATOR = "|"


def parse_cursor(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    """
    El cursor de vuelta, o `(None, None)` si no vale.

    Un cursor corrupto devuelve la primera pagina en lugar de un error: lo peor
    que le pasa a quien manipule el parametro es empezar por arriba.

    La fecha se deja **sin zona horaria** aunque venga con ella. El cursor llega
    del cliente, que puede mandar `...+02:00` a mano, y comparar una fecha con
    zona contra las de la base de datos —que no la llevan— revienta con
    `TypeError` y tumba la peticion entera. Se convierte a UTC y se le quita la
    zona, que deja el mismo instante en la escala que usa el resto.
    """
    if not cursor:
        return None, None
    try:
        fecha, id_raw = cursor.split(CURSOR_SEPARATOR, 1)
        parsed = datetime.fromisoformat(fecha)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed, UUID(id_raw)
    except (ValueError, AttributeError):
        return None, None


def build_cursor(eventos: list[ActivityEvent], limit: int) -> str | None:
    """
    Por donde seguir, o None si esta pagina ya era la ultima.

    Solo se devuelve cursor cuando la pagina vino llena: una pagina a medias
    significa que no queda nada detras, y dar cursor ahi haria que el cliente
    pidiera una pagina vacia solo para descubrirlo.
    """
    if len(eventos) < limit:
        return None
    ultimo = eventos[-1]
    return f"{ultimo.occurred_at.isoformat()}{CURSOR_SEPARATOR}{ultimo.id}"
