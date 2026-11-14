"""
Corta el cuerpo de una subida en cuanto pasa de su tope, mientras llega (CodeRabbit en
BE #774).

El fast-fail por Content-Length (main.py) no ve una subida `chunked` sin esa cabecera:
Starlette parseaba el multipart entero, guardando el fichero en /tmp, antes de que la
ruta leyera con tope. Este middleware ASGI cuenta los bytes que llegan a las rutas de
subida y, en cuanto pasan del tope más el margen del multipart, responde 413 y le dice
a la app que el cliente se fue: el parseo se para ahí. La comprobación exacta del
tamaño del fichero sigue en `read_upload_within_limit`.

Con `tope_general`, cualquier otro cuerpo tiene también su tope (auditoría de la fase 6,
B-04): FastAPI lee y parsea el JSON entero antes de las dependencias y del limitador, y
la API tiene un solo proceso. Lo que declara un Content-Length mayor se rechaza sin leer;
lo que llega por trozos, al pasar el tope.
"""

import json
from collections.abc import Mapping

from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MENSAJE_GENERAL = "La petición es demasiado grande"


class LimitaElCuerpoDeLasSubidas:
    """Middleware ASGI: 413 en cuanto un cuerpo pasa su tope (el de su subida o el general)."""

    def __init__(
        self,
        app: ASGIApp,
        limites: Mapping[str, int],
        margen: int,
        tope_general: int | None = None,
    ) -> None:
        """
        Args:
            app: La aplicación envuelta
            limites: Ruta exacta -> tope del fichero en bytes (solo POST)
            margen: Lo que ocupa el multipart además del fichero (fronteras, cabeceras)
            tope_general: El tope de cualquier otro cuerpo, en bytes; None, sin tope
        """
        self.app = app
        self._limites = dict(limites)
        self._margen = margen
        self._tope_general = tope_general

    def _maximo_y_mensaje(self, scope: Scope) -> tuple[int, bytes] | None:
        """Lo que puede ocupar el cuerpo de esta petición y el 413 que toca, o None."""
        if scope["type"] != "http":
            return None
        tope = self._limites.get(scope.get("path", ""))
        if tope is not None and scope.get("method") == "POST":
            return tope + self._margen, _cuerpo_del_413(
                f"El archivo supera el tamaño máximo permitido ({tope // (1024 * 1024)}MB)"
            )
        if self._tope_general is None:
            return None
        return self._tope_general, _cuerpo_del_413(MENSAJE_GENERAL)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Deja pasar lo que no tiene tope; lo demás lo cuenta y lo corta."""
        limite = self._maximo_y_mensaje(scope)
        if limite is None:
            await self.app(scope, receive, send)
            return
        maximo, cuerpo_del_413 = limite

        # Lo que declara pasarse ni se lee
        if _declarado(scope) > maximo:
            await _responde_413(send, cuerpo_del_413)
            return

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
                    await _responde_413(send, cuerpo_del_413)
                    return {"type": "http.disconnect"}
            return mensaje

        async def envia(mensaje: Message) -> None:
            """Lo que responda la app tras el corte se descarta: ya se respondió 413."""
            if not cortado:
                await send(mensaje)

        try:
            await self.app(scope, recibe, envia)
        except ClientDisconnect:
            # El «cliente se fue» lo dijo este middleware al cortar, y ya respondió 413:
            # no es un error de la app (ni del log ni de Sentry)
            if not cortado:
                raise


def _declarado(scope: Scope) -> int:
    """El Content-Length que declara la petición; -1 si no lo declara o no es un número."""
    for nombre, valor in scope.get("headers", []):
        if nombre == b"content-length":
            try:
                return int(valor)
            except ValueError:
                return -1
    return -1


def _cuerpo_del_413(detalle: str) -> bytes:
    """El JSON del 413."""
    return json.dumps({"detail": detalle}, ensure_ascii=False).encode()


async def _responde_413(send: Send, cuerpo: bytes) -> None:
    """El 413, con la conexión cerrada: lo que quede del cuerpo no se lee."""
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
