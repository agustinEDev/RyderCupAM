"""
El esquema de la petición tras el proxy que termina el TLS (P-03, auditoría del 16 nov 2026).

Render (y antes Cloudflare) termina el HTTPS y habla http con uvicorn, así que la app cree
que todo llega por http y cualquier URL absoluta que construya baja a http://. Se notaba
en la redirección de la barra final: `GET https://api.../api/v1/countries/` contestaba
`307 Location: http://api.../api/v1/countries`.

`uvicorn --proxy-headers` lo arreglaría, pero reescribe también `client` con
X-Forwarded-For, y la IP del cliente se decide en un solo sitio (ADR-038,
`cloudflare_client_ip`, el cubo compartido del rate limit): cambiarla de paso no. Este
middleware solo mira X-Forwarded-Proto y solo SUBE a https (o wss). Decide el ÚLTIMO
valor, el del proxy más cercano (Render); el primero lo puede escribir el cliente. Nunca
baja de https a http.

Cambia el esquema en el mismo scope, como uvicorn con --proxy-headers: así los middlewares
de fuera (y Sentry) ven https y también lo que la app añade al scope (`route`,
`endpoint`, `state`).
"""

from starlette.types import ASGIApp, Receive, Scope, Send

_SEGURO = {"http": "https", "websocket": "wss"}


class EsquemaDelProxy:
    """Middleware ASGI: https (wss) si el proxy dice que la petición le llegó por https."""

    def __init__(self, app: ASGIApp) -> None:
        """
        Args:
            app: La aplicación envuelta
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Cambia solo el esquema, en el mismo scope; el resto llega igual."""
        seguro = _SEGURO.get(scope["type"])
        if seguro is not None and _vino_por_https(scope):
            scope["scheme"] = seguro
        await self.app(scope, receive, send)


def _vino_por_https(scope: Scope) -> bool:
    """Si el último valor de X-Forwarded-Proto (el del proxy más cercano) es https."""
    ultimo = b""
    for nombre, valor in scope.get("headers", []):
        if nombre == b"x-forwarded-proto":
            ultimo = valor.split(b",")[-1]
    return ultimo.strip().lower() == b"https"
