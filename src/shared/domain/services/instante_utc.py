"""
Un instante en UTC con su zona (H5, 25 oct 2026).

Las fechas de la partida rápida se guardan sin zona y en UTC (BE #635). Así
viajaban sin zona, y el navegador las tomaba como hora local: un instante de las
22:30 UTC salía como las 22:30 de Madrid. Con la zona, el cliente lo pone en su
hora local.
"""

from datetime import UTC, datetime


def en_utc(instante: datetime | None) -> datetime | None:
    """Sin zona se entiende UTC; con otra zona se pasa a UTC."""
    if instante is None:
        return None
    if instante.tzinfo is None:
        return instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC)


def ahora_utc_sin_zona() -> datetime:
    """
    Ahora, en UTC y sin zona: como se guardan las fechas de la partida rápida
    (BE #635). `datetime.now()` daba la hora LOCAL del servidor, que solo es UTC
    en Render; en otra zona las fechas salían desplazadas.
    """
    return datetime.now(UTC).replace(tzinfo=None)
