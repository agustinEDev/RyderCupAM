"""
Cabeceras de seguridad HTTP de todas las respuestas de la API.

OWASP Top 10 2021: A02 (HSTS fuerza HTTPS) y A05 (Security Misconfiguration).
"""

from secure import Secure
from starlette.responses import Response

_secure_headers = Secure()


def apply_security_headers(response: Response) -> None:
    """
    Añade las cabeceras de seguridad a la respuesta.

    Algunas rutas (p. ej. las imágenes de preset de avatar, assets inmutables)
    fijan su propio Cache-Control antes de llegar aquí; sin esto, el
    Cache-Control: no-store de la política lo pisaría siempre.
    """
    route_cache_control = response.headers.get("cache-control")
    _secure_headers.framework.fastapi(response)
    if route_cache_control is not None:
        response.headers["cache-control"] = route_cache_control
