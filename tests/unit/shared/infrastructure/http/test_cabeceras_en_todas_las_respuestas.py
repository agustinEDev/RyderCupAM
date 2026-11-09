"""
Las cabeceras de seguridad en TODAS las respuestas de la app (F-15, auditoría OWASP del
9 nov 2026).

El middleware de las cabeceras se registraba el primero, así que era el más interno:
el 403 del CSRF, la respuesta del preflight de CORS y el 500 del UnhandledErrorMiddleware
salían sin ellas. Ahora es el más externo. Y la API manda una CSP que no deja cargar
nada ni enmarcarla, salvo en las páginas de la documentación, que cargan sus scripts.
"""

import base64

import pytest
from fastapi.testclient import TestClient

import main

CSP = "default-src 'none'; frame-ancestors 'none'"
COMUNES = ("strict-transport-security", "x-content-type-options", "x-frame-options")


@pytest.fixture
def cliente():
    """La app real, sin lanzar al test las excepciones del servidor."""
    return TestClient(main.app, raise_server_exceptions=False)


def _con_cabeceras(respuesta) -> None:
    """La respuesta lleva las cabeceras de siempre y la CSP de la API."""
    for cabecera in COMUNES:
        assert cabecera in respuesta.headers, cabecera
    assert respuesta.headers["content-security-policy"] == CSP


def test_a_200_has_the_headers(cliente):
    """
    Given: La app
    When: GET /health (200)
    Then: Lleva las cabeceras de seguridad y la CSP
    """
    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    _con_cabeceras(respuesta)


def test_a_csrf_403_has_the_headers(cliente, monkeypatch):
    """
    Given: El CSRF encendido (TEST_CSRF, como en los tests de seguridad)
    When: Un POST sin token CSRF (403 del middleware, antes de la ruta)
    Then: El 403 lleva las cabeceras de seguridad y la CSP
    """
    monkeypatch.setenv("TEST_CSRF", "true")

    respuesta = cliente.post("/api/v1/competitions", json={})

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "CSRF_VALIDATION_FAILED"
    _con_cabeceras(respuesta)


def test_a_500_has_the_headers(cliente, monkeypatch):
    """
    Given: Una ruta que revienta con un error no controlado
    When: Se pide (500 del UnhandledErrorMiddleware)
    Then: El 500 lleva las cabeceras de seguridad y la CSP
    """

    def _revienta() -> str:
        raise RuntimeError("roto")

    monkeypatch.setattr(main, "get_deployed_commit", _revienta)

    respuesta = cliente.get("/health")

    assert respuesta.status_code == 500
    _con_cabeceras(respuesta)


def test_a_cors_preflight_has_the_headers(cliente):
    """
    Given: Un origen permitido en desarrollo
    When: Llega su preflight (lo contesta el middleware de CORS)
    Then: La respuesta lleva las cabeceras de seguridad y la CSP
    """
    respuesta = cliente.options(
        "/api/v1/competitions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"
    _con_cabeceras(respuesta)


@pytest.mark.parametrize("ruta", ["/docs", "/redoc"])
def test_the_docs_pages_have_no_csp_but_keep_the_rest(cliente, monkeypatch, ruta):
    """
    Given: Las páginas de la documentación, que cargan sus scripts de un CDN
    When: Se piden con sus credenciales
    Then: Sin CSP (las rompería) y con las demás cabeceras
    """
    monkeypatch.setattr(main.settings, "DOCS_USERNAME", "u")
    monkeypatch.setattr(main.settings, "DOCS_PASSWORD", "p")
    basic = base64.b64encode(b"u:p").decode()

    respuesta = cliente.get(ruta, headers={"Authorization": f"Basic {basic}"})

    assert respuesta.status_code == 200
    assert "content-security-policy" not in respuesta.headers
    for cabecera in COMUNES:
        assert cabecera in respuesta.headers
