"""
El CSRF solo se apaga con TESTING en un desarrollo declarado (F-06, auditoría OWASP del
9 nov 2026).

Los tests de integración lo apagan con TESTING=true (y ENVIRONMENT=development, que pone
el conftest). Un TESTING olvidado en producción ya no arranca la app; y aunque llegara a
ella, aquí tampoco apaga nada.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.infrastructure.middleware.csrf_middleware import CSRFMiddleware


def _cliente() -> TestClient:
    """Una app mínima con el middleware CSRF y una ruta que escribe."""
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.post("/api/v1/escribe")
    async def escribe() -> dict:
        """Una ruta que escribe, sin exención."""
        return {"ok": True}

    return TestClient(app)


@pytest.mark.parametrize("environment", ["production", None, "staging"])
def test_testing_outside_development_does_not_disable_csrf(monkeypatch, environment):
    """
    Given: TESTING=true fuera de un desarrollo declarado, sin TEST_CSRF
    When: Llega un POST sin token CSRF
    Then: 403: TESTING no apaga el CSRF fuera de desarrollo
    """
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.delenv("TEST_CSRF", raising=False)
    if environment is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", environment)

    respuesta = _cliente().post("/api/v1/escribe")

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "CSRF_VALIDATION_FAILED"


def test_testing_in_development_still_disables_csrf_for_the_tests(monkeypatch):
    """
    Given: TESTING=true y ENVIRONMENT=development (la suite de tests), sin TEST_CSRF
    When: Llega un POST sin token CSRF
    Then: Pasa, como hasta ahora en los tests de integración
    """
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("TEST_CSRF", raising=False)

    assert _cliente().post("/api/v1/escribe").status_code == 200
