"""
Cada 429 queda en el log de seguridad (auditoría de la fase 6, B-06).

`log_rate_limit_exceeded` existía pero no lo llamaba nadie: un abuso que chocaba
con los límites no dejaba rastro de auditoría. Hay 429 de slowapi y 429 que las
rutas devuelven por su cuenta (búsqueda por correo, cambios de seguridad,
contacto, invitaciones): un middleware apunta todos, vengan de donde vengan.

    caso                                         | qué pasa
    ---------------------------------------------|-----------------------------------
    L1 se supera un límite de slowapi            | evento con la plantilla de la ruta
    L1b una ruta responde 429 por su cuenta      | evento igual
    L2 una respuesta que no es 429               | ningún evento
    L3 el log falla                              | la respuesta sale igual
    L4 la respuesta                              | idéntica a la de antes (cuerpo y código)
    L5 la app real                               | lleva el middleware
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.config.rate_limit import limiter
from src.shared.infrastructure.http import limite_superado


def _app(con_middleware: bool = True) -> tuple[FastAPI, str]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    if con_middleware:
        app.add_middleware(limite_superado.ApuntaLosLimitesSuperados)
    sufijo = uuid4().hex

    @app.get(f"/limitada-{sufijo}/{{item_id}}")
    @limiter.limit("1/minute")
    async def limitada(request: Request, item_id: str):
        return {"ok": True}

    @app.get(f"/propia-{sufijo}")
    async def propia():
        return JSONResponse(status_code=429, content={"detail": "Demasiadas"})

    @app.get(f"/normal-{sufijo}")
    async def normal():
        return {"ok": True}

    return app, sufijo


def test_l1_un_429_de_slowapi_queda_con_la_plantilla_de_la_ruta():
    log = MagicMock()
    app, sufijo = _app()
    cliente = TestClient(app)

    with patch.object(limite_superado, "get_security_logger", return_value=log):
        cliente.get(f"/limitada-{sufijo}/abc")
        respuesta = cliente.get(f"/limitada-{sufijo}/abc")

    assert respuesta.status_code == 429
    log.log_rate_limit_exceeded.assert_called_once()
    datos = log.log_rate_limit_exceeded.call_args.kwargs
    # La plantilla, no los ids concretos que manda el cliente
    assert datos["endpoint"] == f"/limitada-{sufijo}/{{item_id}}"
    assert datos["ip_address"]


def test_l1b_un_429_propio_de_una_ruta_tambien_queda():
    log = MagicMock()
    app, sufijo = _app()

    with patch.object(limite_superado, "get_security_logger", return_value=log):
        respuesta = TestClient(app).get(f"/propia-{sufijo}")

    assert respuesta.status_code == 429
    log.log_rate_limit_exceeded.assert_called_once()
    assert log.log_rate_limit_exceeded.call_args.kwargs["endpoint"] == f"/propia-{sufijo}"


def test_l2_una_respuesta_normal_no_se_apunta():
    log = MagicMock()
    app, sufijo = _app()

    with patch.object(limite_superado, "get_security_logger", return_value=log):
        respuesta = TestClient(app).get(f"/normal-{sufijo}")

    assert respuesta.status_code == 200
    log.log_rate_limit_exceeded.assert_not_called()


def test_l3_si_el_log_falla_la_respuesta_sale_igual():
    log = MagicMock()
    log.log_rate_limit_exceeded.side_effect = RuntimeError("disco lleno")
    app, sufijo = _app()

    with patch.object(limite_superado, "get_security_logger", return_value=log):
        respuesta = TestClient(app).get(f"/propia-{sufijo}")

    assert respuesta.status_code == 429
    assert respuesta.json() == {"detail": "Demasiadas"}


def test_l4_la_respuesta_es_la_misma_con_y_sin_middleware():
    con, sufijo_con = _app()
    sin, sufijo_sin = _app(con_middleware=False)
    cliente_con, cliente_sin = TestClient(con), TestClient(sin)

    with patch.object(limite_superado, "get_security_logger", return_value=MagicMock()):
        cliente_con.get(f"/limitada-{sufijo_con}/x")
        nueva = cliente_con.get(f"/limitada-{sufijo_con}/x")
    cliente_sin.get(f"/limitada-{sufijo_sin}/x")
    vieja = cliente_sin.get(f"/limitada-{sufijo_sin}/x")

    assert nueva.status_code == vieja.status_code == 429
    assert nueva.json() == vieja.json()


def test_l5_la_app_real_lleva_el_middleware():
    from main import app

    assert any(m.cls is limite_superado.ApuntaLosLimitesSuperados for m in app.user_middleware)
