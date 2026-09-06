"""
Lectura de enteros de configuración desde el entorno, tolerante a valores mal puestos.

Estas variables se leen al importar el módulo que las usa: antes de que haya logging
configurado y antes de que la app pueda contestar nada. Un `int()` directo sobre un valor
vacío o con una errata tumba el contenedor con una traza pelada y sin pista de cuál de
ellas fue —y en Render, vaciar una variable es justo la forma natural de desactivarla—.
Es preferible arrancar con el valor por defecto y dejar el aviso escrito.
"""

import logging
import os

logger = logging.getLogger(__name__)


def env_int(name: str, default: int, minimum: int = 1) -> int:
    """
    Lee una variable de entorno como entero, cayendo al valor por defecto si no vale.

    Args:
        name: Nombre de la variable de entorno
        default: Valor a usar si no está definida, está vacía o no es utilizable
        minimum: Valor mínimo aceptable (por debajo se descarta y se usa `default`)

    Returns:
        El entero configurado, o `default` si la variable falta o no sirve.

    Examples:
        >>> env_int("DB_POOL_SIZE", 5)
        5
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s='%s' no es un entero; se usa %d", name, raw, default)
        return default

    if value < minimum:
        logger.warning("%s=%d es menor que el mínimo %d; se usa %d", name, value, minimum, default)
        return default

    return value
