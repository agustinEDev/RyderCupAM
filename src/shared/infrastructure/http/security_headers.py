"""
Cabeceras de seguridad HTTP de todas las respuestas de la API.

OWASP Top 10 2021: A02 (HSTS fuerza HTTPS) y A05 (Security Misconfiguration).

Cada cabecera va explícita. Con secure 2, `Secure()` a secas no pone NINGUNA, y
los valores por defecto (`Secure.with_default_headers()`) cambian el
comportamiento de la API: añaden Cross-Origin-Resource-Policy: same-origin, que
impediría al frontend (www.*) cargar los avatares que sirve api.*; una CSP que
rompería /docs; y quitan Cache-Control: no-store. La política es la que ya
enviaba la API con secure 0.3, fijada en
tests/unit/shared/infrastructure/http/test_security_headers.py.
"""

from secure import (
    CacheControl,
    CustomHeader,
    ReferrerPolicy,
    Secure,
    StrictTransportSecurity,
    XContentTypeOptions,
    XFrameOptions,
)
from starlette.responses import Response

_secure_headers = Secure(
    hsts=StrictTransportSecurity().max_age(63072000).include_subdomains(),  # 2 años
    xfo=XFrameOptions().sameorigin(),
    xcto=XContentTypeOptions().nosniff(),
    referrer=ReferrerPolicy().no_referrer().strict_origin_when_cross_origin(),
    cache=CacheControl().no_store(),
    # "0" desactiva el filtro XSS heredado de los navegadores, que introducía sus
    # propias vulnerabilidades (recomendación actual de OWASP)
    custom=[CustomHeader("X-XSS-Protection", "0")],
)


def apply_security_headers(response: Response) -> None:
    """
    Añade las cabeceras de seguridad a la respuesta.

    Algunas rutas (p. ej. las imágenes de preset de avatar, assets inmutables)
    fijan su propio Cache-Control antes de llegar aquí; sin esto, el
    Cache-Control: no-store de la política lo pisaría siempre.
    """
    route_cache_control = response.headers.get("cache-control")
    _secure_headers.set_headers(response)
    if route_cache_control is not None:
        response.headers["cache-control"] = route_cache_control
