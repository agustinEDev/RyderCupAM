"""
Rechaza con 400 una ruta con una barra codificada, `%2F` o `%5C` (FE-03, fase 4 del plan
a 9; probador de la FE #1098, 11 nov 2026).

Uvicorn decodifica la ruta antes de que Starlette enrute, así que un `%2F` dentro de un id
acaba siendo un separador: `GET /api/v1%2Fcountries` contestaba 200, y un id con `/`
añadía tramos y llegaba a otro endpoint con las cookies de quien navegaba. Ninguna ruta
legítima de la API lleva una barra codificada. Se mira la ruta cruda (`raw_path`), que en
ASGI no trae la búsqueda (va en `query_string`, donde `%2F` es solo texto); sin ella no se
mira nada, porque la ruta ya decodificada no dice si la barra venía codificada. El 400 no
repite la ruta, y deja un aviso en el log con el método, la IP y el correlation id.
"""

import logging

from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from src.shared.infrastructure.http.correlation_middleware import get_correlation_id
from src.shared.infrastructure.http.http_context_validator import cloudflare_client_ip

logger = logging.getLogger(__name__)

_BARRAS_CODIFICADAS = (b"%2f", b"%5c")


class RutaSinBarrasCodificadas:
    """Middleware ASGI: 400 si la ruta cruda lleva `%2F` o `%5C`."""

    def __init__(self, app: ASGIApp) -> None:
        """
        Args:
            app: La aplicación envuelta
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Deja pasar todo salvo las peticiones HTTP con una barra codificada en la ruta."""
        if scope["type"] == "http" and _lleva_barra_codificada(scope):
            _avisa(scope)
            respuesta = JSONResponse(
                status_code=400,
                content={"detail": "Ruta no válida", "error_code": "INVALID_PATH"},
            )
            await respuesta(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _lleva_barra_codificada(scope: Scope) -> bool:
    """Si la ruta cruda lleva `%2F` o `%5C`, en mayúsculas o minúsculas; sin ella, no."""
    cruda = scope.get("raw_path")
    if not cruda:
        return False
    ruta = cruda.lower()
    return any(barra in ruta for barra in _BARRAS_CODIFICADAS)


def _avisa(scope: Scope) -> None:
    """Un aviso de una línea, sin la ruta (puede llevar ids, y la de un sondeo no interesa)."""
    peer = scope.get("client")
    ip = cloudflare_client_ip(Request(scope)) or (peer[0] if peer else "desconocida")
    logger.warning(
        "Ruta con una barra codificada rechazada: %s desde %s (correlation id %s)",
        scope.get("method"),
        ip,
        get_correlation_id(),
    )
