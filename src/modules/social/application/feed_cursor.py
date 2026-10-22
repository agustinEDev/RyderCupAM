"""
El cursor con el que se pagina el feed.

Vive aparte porque lo comparten el feed de amigos y la actividad de un jugador:
son la misma paginacion sobre los mismos eventos, y dos implementaciones se
separarian en cuanto una de las dos cambiara de formato.

El cursor son **dos** valores, fecha e id, y no solo la fecha. Todos los logros
de una misma vuelta se publican con el mismo `published_at` —salen del mismo
instante—, asi que un cursor por fecha sola dejaria fuera los que aun no se han
enseñado de esa vuelta.

La fecha es la de publicacion, por la que se ordena el feed. Antes era la de
juego (`occurred_at`) con el mismo formato; las filas de entonces se rellenaron
con esa misma fecha, asi que un cursor viejo sigue cayendo en su sitio.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
    ActivitySlice,
)

# La fecha en ISO no contiene '|', asi que parte el cursor sin ambiguedad
CURSOR_SEPARATOR = "|"

# Cuanto se mira tras una pagina llena para completar sus tarjetas. Una tarjeta
# son los logros de una vuelta (seis tipos como mucho), pero los de un torneo
# se publican a la vez para todos sus jugadores y se intercalan por id
VENTANA_DE_TARJETAS = 200


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
    return f"{ultimo.published_at.isoformat()}{CURSOR_SEPARATOR}{ultimo.id}"


async def sin_partir_tarjetas(
    events: ActivityEventRepositoryInterface,
    slices: Sequence[ActivitySlice],
    eventos: list[ActivityEvent],
    limit: int,
) -> list[ActivityEvent]:
    """
    La pagina, alargada para que ninguna tarjeta quede partida (E22).

    Si la pagina vino llena, puede que una tarjeta —los logros de una vuelta—
    siga en la siguiente. Se trae lo que viene detras y se añade hasta la
    ultima fila de las tarjetas que ya estan en la pagina, con lo que haya en
    medio: saltarselo lo perderia, porque el cursor sigue tras la ultima fila
    añadida. Lo añadido puede traer tarjetas nuevas partidas, asi que se repite
    hasta que no quede ninguna.
    """
    if len(eventos) < limit:
        return eventos
    ultimo = eventos[-1]
    siguientes = await events.find_in(
        slices, limit=VENTANA_DE_TARJETAS, before=ultimo.published_at, before_id=ultimo.id
    )
    pagina = list(eventos)
    while siguientes:
        abiertas = {e.card_key for e in pagina if e.type.is_achievement}
        hasta = max((i for i, e in enumerate(siguientes) if e.card_key in abiertas), default=None)
        if hasta is None:
            break
        pagina.extend(siguientes[: hasta + 1])
        siguientes = siguientes[hasta + 1 :]
    return pagina
