"""
Un tope de tamaño para TODO cuerpo, no solo para las subidas (auditoría de la fase 6, B-04).

FastAPI lee y parsea el JSON entero antes de que corran las dependencias y el limitador,
y la API tiene un solo proceso: un `POST /auth/login` anónimo de 100 MB podía tumbarla.
Cloudflare ya corta a 256 KB lo que declara su tamaño; esto lo hace también la API, y
corta lo que llega por trozos sin declararlo.

    caso                                                    | qué pasa
    --------------------------------------------------------|---------------------------------
    A1 declara más de 256 KB                                | 413 sin leer el cuerpo
    A2 por trozos, sin declarar, pasa de 256 KB             | 413 al pasar el tope
    A3 200 KB                                               | llega a la ruta
    A4 las subidas siguen con su tope (y su texto)          | 1 MB en el test, no 256 KB
    A5 el 413 general                                       | «La petición es demasiado grande»
    la app real                                             | 256 KB y las dos subidas
"""

import json

import pytest
from fastapi import FastAPI, File, Request, UploadFile

from src.shared.infrastructure.http.limite_del_cuerpo import LimitaElCuerpoDeLasSubidas

pytestmark = pytest.mark.asyncio

KB = 1024
MB = 1024 * KB
SUBIDA = "/subida"
TOPE_SUBIDA = 1 * MB
TOPE_GENERAL = 256 * KB
MARGEN = 16 * KB
TROZO = 64 * KB


def _app() -> LimitaElCuerpoDeLasSubidas:
    """Una ruta JSON cualquiera y una de subida, con los dos topes."""
    app = FastAPI()

    @app.post("/login")
    async def login(request: Request) -> dict:
        """Lee el cuerpo entero, como hace FastAPI con un modelo."""
        return {"bytes": len(await request.body())}

    @app.post(SUBIDA)
    async def sube(file: UploadFile = File(...)) -> dict:
        """Recibe el fichero."""
        return {"bytes": len(await file.read())}

    return LimitaElCuerpoDeLasSubidas(
        app, limites={SUBIDA: TOPE_SUBIDA}, margen=MARGEN, tope_general=TOPE_GENERAL
    )


async def _envia(
    app, ruta: str, cuerpo: bytes, *, declarado: int | None = None, tipo: bytes
) -> tuple[int, int, dict]:
    """Manda `cuerpo` en trozos de 64 KB; con `declarado`, con esa Content-Length."""
    trozos = [cuerpo[i : i + TROZO] for i in range(0, len(cuerpo), TROZO)] or [b""]
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

    cabeceras = [(b"content-type", tipo)]
    if declarado is not None:
        cabeceras.append((b"content-length", str(declarado).encode()))
    alcance = {
        "type": "http",
        "method": "POST",
        "path": ruta,
        "raw_path": ruta.encode(),
        "query_string": b"",
        "headers": cabeceras,
        "client": ("1.2.3.4", 1),
        "server": ("testserver", 80),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
    }
    await app(alcance, recibe, envia)
    return respuesta["estado"], leidos, json.loads(respuesta["cuerpo"] or b"{}")


def _json(tamano: int) -> bytes:
    """Un JSON de unos `tamano` bytes."""
    return b'{"email":"' + b"x" * tamano + b'"}'


async def test_a1_a_declared_body_over_the_general_cap_is_refused_without_reading_it():
    """
    Given: Un login que declara 100 MB
    When: Llega
    Then: 413 sin leer ni un byte: lo dice la cabecera
    """
    estado, leidos, cuerpo = await _envia(
        _app(), "/login", _json(10), declarado=100 * MB, tipo=b"application/json"
    )

    assert estado == 413
    assert leidos == 0
    assert cuerpo == {"detail": "La petición es demasiado grande"}


async def test_a2_a_chunked_body_over_the_general_cap_is_cut_while_it_arrives():
    """
    Given: Un login por trozos, sin Content-Length, de 5 MB
    When: Llega
    Then: 413, y se dejó de leer al pasar los 256 KB (como mucho un trozo más)
    """
    estado, leidos, cuerpo = await _envia(_app(), "/login", _json(5 * MB), tipo=b"application/json")

    assert estado == 413
    assert leidos <= TOPE_GENERAL + TROZO
    assert cuerpo == {"detail": "La petición es demasiado grande"}


async def test_a3_a_body_under_the_general_cap_reaches_the_route():
    """
    Given: Un JSON de 200 KB, declarado
    When: Llega
    Then: La ruta lo lee entero
    """
    datos = _json(200 * KB)
    estado, _, cuerpo = await _envia(
        _app(), "/login", datos, declarado=len(datos), tipo=b"application/json"
    )

    assert (estado, cuerpo) == (200, {"bytes": len(datos)})


async def test_a4_upload_routes_keep_their_own_cap_and_text():
    """
    Given: Una subida de 512 KB (más que el tope general, menos que el de subidas)
    When: Llega
    Then: Pasa; y una de 2 MB se corta con el texto de las subidas
    """
    frontera = b"xyz"

    def multipart(tamano: int) -> bytes:
        return (
            b"--"
            + frontera
            + b'\r\nContent-Disposition: form-data; name="file"; filename="a.jpg"'
            + b"\r\nContent-Type: image/jpeg\r\n\r\n"
            + b"x" * tamano
            + b"\r\n--"
            + frontera
            + b"--\r\n"
        )

    tipo = b"multipart/form-data; boundary=xyz"
    estado, _, cuerpo = await _envia(_app(), SUBIDA, multipart(512 * KB), tipo=tipo)
    assert (estado, cuerpo) == (200, {"bytes": 512 * KB})

    estado, _, cuerpo = await _envia(_app(), SUBIDA, multipart(2 * MB), tipo=tipo)
    assert estado == 413
    assert "1MB" in cuerpo["detail"]


async def test_without_a_general_cap_other_routes_are_not_limited():
    """
    Given: El middleware sin tope general (como antes)
    When: Llega un JSON de 2 MB
    Then: Pasa
    """
    app = FastAPI()

    @app.post("/login")
    async def login(request: Request) -> dict:
        return {"bytes": len(await request.body())}

    limitado = LimitaElCuerpoDeLasSubidas(app, limites={}, margen=MARGEN)
    datos = _json(2 * MB)
    estado, _, _ = await _envia(limitado, "/login", datos, tipo=b"application/json")

    assert estado == 200


def test_the_real_app_caps_every_body_at_256_kb():
    """
    Given: La app real
    When: Se busca el límite del cuerpo entre sus middlewares
    Then: Lleva el tope general de 256 KB, además de las dos subidas
    """
    import main

    [limite] = [m for m in main.app.user_middleware if m.cls is LimitaElCuerpoDeLasSubidas]
    assert limite.kwargs["tope_general"] == 256 * KB


async def test_a_real_disconnect_before_the_cap_still_raises():
    """
    Given: Una ruta que lanza ClientDisconnect sin que el middleware haya cortado
    When: Llega un cuerpo pequeño
    Then: El error sigue su camino: solo se calla el «se fue» del propio corte
    """
    from starlette.requests import ClientDisconnect

    async def se_va(_scope, _receive, _send):
        raise ClientDisconnect

    app = LimitaElCuerpoDeLasSubidas(se_va, limites={}, margen=MARGEN, tope_general=TOPE_GENERAL)

    with pytest.raises(ClientDisconnect):
        await _envia(app, "/login", _json(10), tipo=b"application/json")


async def test_after_the_response_started_the_cut_does_not_send_a_second_start():
    """
    /code-review: una ruta que responde sin leer el cuerpo y sigue escuchando la
    desconexión (como StreamingResponse) no puede recibir un 413 a mitad de su
    respuesta: se corta la lectura y nada más.
    """
    inicios: list[int] = []

    async def responde_sin_leer(_scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        while (await receive())["type"] != "http.disconnect":
            pass
        await send({"type": "http.response.body", "body": b"{}"})

    app = LimitaElCuerpoDeLasSubidas(
        responde_sin_leer, limites={}, margen=MARGEN, tope_general=TOPE_GENERAL
    )
    trozos = [b"x" * TROZO for _ in range(10)]

    async def recibe():
        if not trozos:
            return {"type": "http.disconnect"}
        return {"type": "http.request", "body": trozos.pop(0), "more_body": bool(trozos)}

    async def envia(mensaje):
        if mensaje["type"] == "http.response.start":
            inicios.append(mensaje["status"])

    await app({"type": "http", "method": "POST", "path": "/x", "headers": []}, recibe, envia)

    assert inicios == [200]


async def test_a_declared_upload_over_its_cap_is_refused_without_reading():
    """El fast-fail por Content-Length de las subidas, ahora en este middleware."""
    estado, leidos, cuerpo = await _envia(
        _app(),
        SUBIDA,
        b"x",
        declarado=TOPE_SUBIDA + MARGEN + 1,
        tipo=b"multipart/form-data; boundary=xyz",
    )

    assert estado == 413
    assert leidos == 0
    assert "1MB" in cuerpo["detail"]
