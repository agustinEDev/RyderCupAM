"""
Rate Limiting Configuration

Configuración centralizada de rate limiting para la API.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_client_identifier(request: Request) -> str:
    """
    Obtiene el identificador del cliente para rate limiting.

    En testing: Usa el header X-Test-Client-ID si existe (permite simular diferentes clientes).
    En producción: Usa la IP real del cliente.
    """
    # En testing, permitir simular diferentes clientes con un header especial
    if os.getenv('TESTING', 'false').lower() == 'true':
        test_client_id = request.headers.get('X-Test-Client-ID')
        if test_client_id:
            return test_client_id

    # En producción (o testing sin header especial), usar IP real
    return get_remote_address(request)


# Crear instancia global del limiter
# - key_func: Identifica clientes por IP o header de testing
# - default_limits: Límite global de 100 peticiones/minuto
# NOTE: headers_enabled=False porque causa conflictos con endpoints que retornan DTOs
#       Los headers X-RateLimit-* solo aparecen cuando se excede el límite (HTTP 429)
limiter = Limiter(
    key_func=get_client_identifier,
    default_limits=["100/minute"]
)
