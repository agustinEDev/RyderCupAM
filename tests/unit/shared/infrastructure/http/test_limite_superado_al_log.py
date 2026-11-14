"""
Cada 429 queda en el log de seguridad (auditoría de la fase 6, B-06).

`log_rate_limit_exceeded` existía pero no lo llamaba nadie: un abuso que chocaba
con los límites no dejaba rastro de auditoría.

    caso                                   | qué pasa
    ---------------------------------------|-----------------------------------------
    L1 se supera el límite de una ruta     | 429 y un evento con la ruta y el límite
    L2 la respuesta 429                    | la misma que la de slowapi (cuerpo y código)
    L3 el log falla                        | el 429 sale igual
    L4 la app real                         | registra este manejador para el 429
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.config.rate_limit import limiter
from src.shared.infrastructure.http import limite_superado


def _app(manejador) -> tuple[FastAPI, str]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, manejador)
    ruta = f"/limitada-{uuid4().hex}"

    @app.get(ruta)
    @limiter.limit("1/minute")
    async def limitada(request: Request):
        return {"ok": True}

    return app, ruta


def _dos_veces(app: FastAPI, ruta: str):
    cliente = TestClient(app)
    cliente.get(ruta)
    return cliente.get(ruta)


def test_l1_el_429_queda_en_el_log_de_seguridad():
    log = MagicMock()
    app, ruta = _app(limite_superado.responde_al_limite_superado)

    with patch.object(limite_superado, "get_security_logger", return_value=log):
        respuesta = _dos_veces(app, ruta)

    assert respuesta.status_code == 429
    log.log_rate_limit_exceeded.assert_called_once()
    datos = log.log_rate_limit_exceeded.call_args.kwargs
    assert datos["endpoint"] == ruta
    assert "1" in datos["limit_value"]
    assert datos["ip_address"]


def test_l2_la_respuesta_es_la_misma_que_la_de_slowapi():
    app_nueva, ruta_nueva = _app(limite_superado.responde_al_limite_superado)
    app_vieja, ruta_vieja = _app(_rate_limit_exceeded_handler)

    with patch.object(limite_superado, "get_security_logger", return_value=MagicMock()):
        nueva = _dos_veces(app_nueva, ruta_nueva)
    vieja = _dos_veces(app_vieja, ruta_vieja)

    assert nueva.status_code == vieja.status_code == 429
    assert nueva.json() == vieja.json()


def test_l3_si_el_log_falla_el_429_sale_igual():
    log = MagicMock()
    log.log_rate_limit_exceeded.side_effect = RuntimeError("disco lleno")
    app, ruta = _app(limite_superado.responde_al_limite_superado)

    with patch.object(limite_superado, "get_security_logger", return_value=log):
        respuesta = _dos_veces(app, ruta)

    assert respuesta.status_code == 429


def test_l4_la_app_real_registra_este_manejador():
    from main import app

    assert app.exception_handlers[RateLimitExceeded] is limite_superado.responde_al_limite_superado
