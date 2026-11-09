"""
El cuerpo de una subida se corta al recibirlo, no después (CodeRabbit en BE #774).

El fast-fail por Content-Length no ve una subida `chunked` sin esa cabecera: Starlette
parseaba el multipart entero, guardando el fichero en /tmp, antes de que la ruta
leyera con tope. Ahora un middleware ASGI cuenta los bytes que llegan a las rutas de
subida y, en cuanto pasan del tope más el margen del multipart, responde 413 y deja
de leer. La comprobación exacta del fichero sigue en `read_upload_within_limit`.
"""

import json

import pytest
from fastapi import FastAPI, File, UploadFile

from src.shared.infrastructure.http.limite_del_cuerpo import LimitaElCuerpoDeLasSubidas

pytestmark = pytest.mark.asyncio

KB = 1024
MB = 1024 * KB
RUTA = "/subida"
TOPE = 1 * MB
MARGEN = 16 * KB
TROZO = 64 * KB
LIMITE = 'form-data; name="file"; filename="a.jpg"'


def _app() -> LimitaElCuerpoDeLasSubidas:
    """Una app con una ruta de subida real (Starlette parsea el multipart) y el límite."""
    app = FastAPI()

    @app.post(RUTA)
    async def sube(file: UploadFile = File(...)) -> dict:
        """Recibe el fichero (la ruta no llega a ejecutarse si se corta antes)."""
        return {"bytes": len(await file.read())}

    @app.post("/otra")
    async def otra(file: UploadFile = File(...)) -> dict:
        """Una ruta que no es de subida limitada."""
        return {"bytes": len(await file.read())}

    return LimitaElCuerpoDeLasSubidas(app, limites={RUTA: TOPE}, margen=MARGEN)


def _multipart(tamano: int) -> tuple[bytes, bytes, bytes]:
    """Cabecera, relleno de `tamano` bytes y cierre de un multipart con un fichero."""
    frontera = b"xyz"
    cabeza = (
        b"--"
        + frontera
        + b"\r\nContent-Disposition: "
        + LIMITE.encode()
        + b"\r\nContent-Type: image/jpeg\r\n\r\n"
    )
    return cabeza, b"x" * tamano, b"\r\n--" + frontera + b"--\r\n"


async def _envia(app, ruta: str, tamano: int) -> tuple[int, int, dict]:
    """
    Manda un multipart de `tamano` bytes de fichero en trozos de 64 KB, SIN
    Content-Length (chunked). Devuelve el estado, los bytes que la app llegó a leer y
    el cuerpo de la respuesta.
    """
    cabeza, relleno, cola = _multipart(tamano)
    cuerpo = cabeza + relleno + cola
    trozos = [cuerpo[i : i + TROZO] for i in range(0, len(cuerpo), TROZO)]
    leidos = 0
    respuesta: dict = {"cuerpo": b""}

    async def recibe():
        nonlocal leidos
        if not trozos:
            return {"type": "http.disconnect"}
        trozo = trozos.pop(0)
        leidos += len(trozo)
        return {"type": "http.request", "body": trozo, "more_body": bool(trozos)}

    async def envia(mensaje):
        if mensaje["type"] == "http.response.start":
            respuesta["estado"] = mensaje["status"]
        elif mensaje["type"] == "http.response.body":
            respuesta["cuerpo"] += mensaje.get("body", b"")

    alcance = {
        "type": "http",
        "method": "POST",
        "path": ruta,
        "raw_path": ruta.encode(),
        "query_string": b"",
        "headers": [(b"content-type", b"multipart/form-data; boundary=xyz")],
        "client": ("1.2.3.4", 1),
        "server": ("testserver", 80),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
    }
    await app(alcance, recibe, envia)
    return respuesta["estado"], leidos, json.loads(respuesta["cuerpo"] or b"{}")


async def test_a_chunked_upload_over_the_cap_is_cut_while_it_arrives():
    """
    Given: Una subida chunked de 50 MB a una ruta con tope de 1 MB
    When: Llega
    Then: 413, y la app dejó de leer al pasar el tope más el margen (como mucho un
          trozo más): el cuerpo no llega entero a /tmp
    """
    estado, leidos, cuerpo = await _envia(_app(), RUTA, 50 * MB)

    assert estado == 413
    assert leidos <= TOPE + MARGEN + TROZO
    assert "1MB" in cuerpo["detail"]


async def test_an_upload_within_the_cap_reaches_the_route():
    """
    Given: Una subida chunked de 512 KB (tope 1 MB)
    When: Llega
    Then: La ruta la recibe entera
    """
    estado, _, cuerpo = await _envia(_app(), RUTA, 512 * KB)

    assert (estado, cuerpo) == (200, {"bytes": 512 * KB})


async def test_other_routes_are_not_limited():
    """
    Given: Una subida de 2 MB a una ruta que no está en la lista
    When: Llega
    Then: Pasa: el límite es solo para las rutas de subida
    """
    estado, _, cuerpo = await _envia(_app(), "/otra", 2 * MB)

    assert (estado, cuerpo) == (200, {"bytes": 2 * MB})


def test_the_app_limits_both_upload_routes():
    """
    Given: La app real
    When: Se busca el límite del cuerpo entre sus middlewares
    Then: Está, con el avatar y la galería y su tope de siempre
    """
    import main

    [limite] = [m for m in main.app.user_middleware if m.cls is LimitaElCuerpoDeLasSubidas]
    assert limite.kwargs["limites"] == main._UPLOAD_SIZE_LIMITS
    assert set(main._UPLOAD_SIZE_LIMITS) == {
        "/api/v1/users/me/avatar/upload",
        "/api/v1/users/me/photos",
    }
    assert limite.kwargs["margen"] == main._MAX_AVATAR_MULTIPART_OVERHEAD_BYTES


async def test_after_the_cut_an_app_that_keeps_reading_gets_nothing_more():
    """
    Given: Una app que sigue pidiendo cuerpo aunque le digan que el cliente se fue
    When: Llega una subida chunked de 50 MB (tope 1 MB)
    Then: Tras el corte solo recibe «desconectado»: no se lee ni un byte más
    """

    async def insistente(_scope, receive, send):
        for _ in range(2000):
            await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    app = LimitaElCuerpoDeLasSubidas(insistente, limites={RUTA: TOPE}, margen=MARGEN)

    estado, leidos, _ = await _envia(app, RUTA, 50 * MB)

    assert estado == 413
    assert leidos <= TOPE + MARGEN + TROZO
