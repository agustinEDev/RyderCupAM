"""
El middleware rechaza un token CSRF caducado o con la hora tocada (F-19, auditoría OWASP
del 9 nov 2026), con el mismo 403 CSRF_VALIDATION_FAILED, que el front ya sabe
recuperar refrescando la sesión.
"""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config.csrf_config import generate_csrf_token
from src.shared.infrastructure.middleware import csrf_middleware
from src.shared.infrastructure.middleware.csrf_middleware import CSRFMiddleware

A = "11111111-1111-1111-1111-111111111111"
DIA = 24 * 60 * 60


@pytest.fixture
def envia(monkeypatch):
    """Manda un POST con la sesión de A y el token dado en cabecera y cookie."""
    monkeypatch.setenv("TEST_CSRF", "true")
    monkeypatch.setattr(csrf_middleware, "usuarios_de_la_sesion", lambda _peticion: {A})
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.post("/api/v1/escribe")
    async def escribe() -> dict:
        """Una ruta que escribe, sin exención."""
        return {"ok": True}

    cliente = TestClient(app)

    def _envia(token: str):
        cliente.cookies.set("csrf_token", token)
        return cliente.post("/api/v1/escribe", headers={"X-CSRF-Token": token})

    return _envia


def test_a_fresh_token_passes(envia):
    """
    Given: La sesión de A y un token recién emitido para A
    When: Hace un POST
    Then: Pasa el CSRF
    """
    assert envia(generate_csrf_token(A)).status_code == 200


def test_an_8_day_old_token_is_403(envia):
    """
    Given: La sesión de A y un token suyo de hace 8 días
    When: Hace un POST
    Then: 403 CSRF_VALIDATION_FAILED
    """
    respuesta = envia(generate_csrf_token(A, ahora=time.time() - 8 * DIA))

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "CSRF_VALIDATION_FAILED"


def test_a_token_with_a_tampered_issue_time_is_403(envia):
    """
    Given: La sesión de A y un token suyo viejo con la hora cambiada a ahora
    When: Hace un POST
    Then: 403 CSRF_VALIDATION_FAILED
    """
    aleatorio, _, firma = generate_csrf_token(A, ahora=time.time() - 8 * DIA).split(".")

    respuesta = envia(f"{aleatorio}.{int(time.time())}.{firma}")

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "CSRF_VALIDATION_FAILED"
