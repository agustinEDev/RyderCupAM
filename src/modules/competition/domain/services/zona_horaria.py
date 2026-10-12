"""
La zona horaria de un campo, a partir de su nombre IANA (BE #502).

Estaba copiada en la apertura de la anotación y en la de inscripciones, y el
refresco de las 3:00 iba a ser la tercera. Una zona que no existe no puede
tumbar nada: se avisa en el registro y se trata como si no se supiera.
"""

import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)


def zona_del_campo(nombre: str | None) -> ZoneInfo | None:
    """La zona, o None si no hay nombre o no existe."""
    if nombre is None:
        return None
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        logger.warning("Zona horaria desconocida en un campo: %s", nombre)
        return None
