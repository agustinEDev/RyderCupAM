"""
Corta el cuerpo de una subida en cuanto pasa de su tope, mientras llega (CodeRabbit en
BE #774).

El fast-fail por Content-Length (main.py) no ve una subida `chunked` sin esa cabecera:
Starlette parseaba el multipart entero, guardando el fichero en /tmp, antes de que la
ruta leyera con tope. Este middleware ASGI cuenta los bytes que llegan a las rutas de
subida y, en cuanto pasan del tope más el margen del multipart, responde 413 y le dice
a la app que el cliente se fue: el parseo se para ahí. La comprobación exacta del
tamaño del fichero sigue en `read_upload_within_limit`.
"""

import json
from collections.abc import Mapping

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class LimitaElCuerpoDeLasSubidas:
    """Middleware ASGI: 413 en cuanto el cuerpo de una ruta de subida pasa su tope."""

    def __init__(self, app: ASGIApp, limites: Mapping[str, int], margen: int) -> None:
        """
        Args:
            app: La aplicación envuelta
            limites: Ruta exacta -> tope del fichero en bytes (solo POST)
            margen: Lo que ocupa el multipart además del fichero (fronteras, cabeceras)
        """
        self.app = app
        self._limites = dict(limites)
        self._margen = margen

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Deja pasar todo salvo los POST a las rutas de subida, que cuenta y corta."""
        tope = self._limites.get(scope.get("path", "")) if scope["type"] == "http" else None
        if tope is None or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        maximo = tope + self._margen
        recibidos = 0
        cortado = False

        async def recibe() -> Message:
            """El cuerpo, contado; pasado el máximo, 413 y «el cliente se fue»."""
            nonlocal recibidos, cortado
            if cortado:
                return {"type": "http.disconnect"}
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibidos += len(mensaje.get("body", b""))
                if recibidos > maximo:
                    cortado = True
                    await _responde_413(send, tope)
                    return {"type": "http.disconnect"}
            return mensaje

        async def envia(mensaje: Message) -> None:
            """Lo que responda la app tras el corte se descarta: ya se respondió 413."""
            if not cortado:
                await send(mensaje)

        await self.app(scope, recibe, envia)


async def _responde_413(send: Send, tope: int) -> None:
    """El mismo 413 que el fast-fail por Content-Length."""
    cuerpo = json.dumps(
        {"detail": f"El archivo supera el tamaño máximo permitido ({tope // (1024 * 1024)}MB)"},
        ensure_ascii=False,
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(cuerpo)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": cuerpo})
