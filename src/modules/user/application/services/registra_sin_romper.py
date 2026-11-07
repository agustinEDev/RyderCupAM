"""
Registrar en el log de seguridad sin que un fallo suyo cambie la respuesta (#750).

El rastro importa, pero una petición rechazada tiene que seguir siéndolo (y una buena,
buena): si el log falla, se apunta en el log normal, sin datos, y la petición sigue.
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def registra_sin_romper(que: str, registro: Callable[[], object]) -> None:
    """Hace `registro`; si falla, solo lo apunta (con el tipo del error, nunca el mensaje)."""
    try:
        registro()
    except Exception as error:
        logger.error("%s audit event failed: %s", que, type(error).__name__)
