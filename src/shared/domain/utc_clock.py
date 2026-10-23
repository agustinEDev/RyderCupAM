"""La hora actual tal como se guardan las fechas: en UTC y sin zona."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """
    Ahora, en UTC y sin zona.

    Las columnas de fecha no llevan zona y guardan UTC; comparar con una fecha
    con zona revienta, y con la hora local queda desplazada lo que separe al
    servidor de UTC. Un solo sitio para no repetir el `replace(tzinfo=None)`.
    """
    return datetime.now(UTC).replace(tzinfo=None)
