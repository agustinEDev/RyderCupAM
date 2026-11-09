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

Desde F-15 (auditoría OWASP del 9 nov 2026), además, una CSP que no deja cargar nada
ni enmarcar la respuesta: la API solo sirve JSON e imágenes. Salvo en /docs y /redoc,
cuyas páginas cargan sus scripts de un CDN.
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


CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'"

# Las páginas de la documentación: cargan Swagger UI y ReDoc de un CDN. Exactas
_PAGINAS_SIN_CSP = frozenset({"/docs", "/redoc"})


def apply_security_headers(response: Response, path: str | None = None) -> None:
    """
    Añade las cabeceras de seguridad a la respuesta.

    Algunas rutas (p. ej. las imágenes de preset de avatar, assets inmutables)
    fijan su propio Cache-Control antes de llegar aquí; sin esto, el
    Cache-Control: no-store de la política lo pisaría siempre.

    Args:
        response: La respuesta
        path: La ruta pedida; /docs y /redoc salen sin la CSP
    """
    route_cache_control = response.headers.get("cache-control")
    _secure_headers.set_headers(response)
    if route_cache_control is not None:
        response.headers["cache-control"] = route_cache_control
    if path is None or (path.rstrip("/") or "/") not in _PAGINAS_SIN_CSP:
        response.headers["content-security-policy"] = CONTENT_SECURITY_POLICY
