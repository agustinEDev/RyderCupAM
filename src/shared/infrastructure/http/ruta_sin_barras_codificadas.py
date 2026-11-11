"""
Rechaza con 400 una ruta con una barra codificada, `%2F` o `%5C` (FE-03, fase 4 del plan
a 9; probador de la FE #1098, 11 nov 2026).

Uvicorn decodifica la ruta antes de que Starlette enrute, así que un `%2F` dentro de un id
acaba siendo un separador: `GET /api/v1%2Fcountries` contestaba 200, y un id con `/`
añadía tramos y llegaba a otro endpoint con las cookies de quien navegaba. Ninguna ruta
legítima de la API lleva una barra codificada. Se mira la ruta cruda (`raw_path`), que en
ASGI no trae la búsqueda (va en `query_string`, donde `%2F` es solo texto). El 400 no
repite la ruta.
"""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

_BARRAS_CODIFICADAS = (b"%2f", b"%5c")
_CUERPO = json.dumps(
    {"detail": "Ruta no válida", "error_code": "INVALID_PATH"}, ensure_ascii=False
).encode()


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
            await _responde_400(send)
            return
        await self.app(scope, receive, send)


def _lleva_barra_codificada(scope: Scope) -> bool:
    """Si la ruta cruda lleva `%2F` o `%5C`, en mayúsculas o minúsculas."""
    ruta = (scope.get("raw_path") or scope.get("path", "").encode()).lower()
    return any(barra in ruta for barra in _BARRAS_CODIFICADAS)


async def _responde_400(send: Send) -> None:
    """El 400 con el formato de los errores de la API."""
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_CUERPO)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _CUERPO})
