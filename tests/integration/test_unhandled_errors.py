"""
Un error no controlado responde 500 con cabeceras CORS (FE #710).

Sin esto, la excepción subía hasta el `ServerErrorMiddleware` de Starlette,
que va POR FUERA del CORS: el 500 salía sin `Access-Control-Allow-Origin`, el
navegador lo bloqueaba como «Failed to fetch» y el frontend decía «Sin
conexión» con la red funcionando.

    #   caso                                   | qué pasa
    ----|--------------------------------------|---------------------------------------
    U1  una excepción no controlada            | 500 en JSON, con las cabeceras CORS
    U2  su mensaje                             | no sale en la respuesta (OWASP A05)
    U3  el error                               | se registra con su traza (llega a Sentry)
    U4  un error HTTP normal (404)             | no se toca
"""

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = pytest.mark.asyncio

RUTA = "/__test__/revienta"
ORIGEN = "http://localhost:5173"


@pytest.fixture
async def cliente():
    async def revienta():
        raise RuntimeError("detalle interno que no debe salir")

    app.add_api_route(RUTA, revienta, methods=["GET"])
    try:
        # raise_app_exceptions=False: si algo se escapa, se ve como 500 del
        # middleware de Starlette y no como una excepción del test
        transporte = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transporte, base_url="http://test") as c:
            yield c
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != RUTA]


async def test_u1_el_500_lleva_las_cabeceras_cors(cliente):
    respuesta = await cliente.get(RUTA, headers={"Origin": ORIGEN})

    assert respuesta.status_code == 500
    assert respuesta.headers.get("access-control-allow-origin") == ORIGEN
    assert respuesta.json()["error_code"] == "INTERNAL_ERROR"
    # Y su id de correlación, para cruzarlo con el evento de Sentry (CodeRabbit)
    assert respuesta.headers.get("x-correlation-id")


async def test_u2_no_cuenta_el_detalle_interno(cliente):
    respuesta = await cliente.get(RUTA, headers={"Origin": ORIGEN})

    assert "detalle interno" not in respuesta.text
    assert "RuntimeError" not in respuesta.text


async def test_u3_se_registra_con_su_traza(cliente, caplog):
    with caplog.at_level(logging.ERROR):
        await cliente.get(RUTA, headers={"Origin": ORIGEN})

    errores = [r for r in caplog.records if r.levelno >= logging.ERROR and r.exc_info]
    assert errores, "el error tiene que registrarse con su traza para que llegue a Sentry"
    assert isinstance(errores[0].exc_info[1], RuntimeError)


async def test_u4_un_404_no_se_toca(cliente):
    respuesta = await cliente.get("/__test__/no-existe", headers={"Origin": ORIGEN})

    assert respuesta.status_code == 404
    assert respuesta.json() != {
        "detail": "Error interno del servidor",
        "error_code": "INTERNAL_ERROR",
    }
