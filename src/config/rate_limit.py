"""
Rate Limiting Configuration

Configuración centralizada de rate limiting para la API.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Crear instancia global del limiter
# - key_func: Identifica clientes por dirección IP
# - default_limits: Límite global de 100 peticiones/minuto
# NOTE: headers_enabled=False porque causa conflictos con endpoints que retornan DTOs
#       Los headers X-RateLimit-* solo aparecen cuando se excede el límite (HTTP 429)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"]
)
