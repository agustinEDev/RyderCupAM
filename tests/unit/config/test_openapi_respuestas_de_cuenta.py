"""
Las rutas de cuenta documentan en OpenAPI las respuestas con código que devuelven.

El probador de la release (8 nov 2026) vio que `PATCH /users/security` devolvía 401 y
409 con `error_code` sin documentarlos, y lo mismo el 401/423 del login y el 400 de
desvincular Google: quien lea `/docs` no sabría qué esperar.
"""

import pytest

from main import app as fastapi_app


@pytest.mark.parametrize(
    ("ruta", "metodo", "codigos"),
    [
        ("/api/v1/users/security", "patch", {"401", "409", "429"}),
        ("/api/v1/auth/login", "post", {"401", "403", "423"}),
        ("/api/v1/auth/google/unlink", "delete", {"400"}),
    ],
)
def test_the_account_route_documents_its_error_responses(ruta, metodo, codigos):
    """
    Given: El esquema OpenAPI de la app
    When: Se mira una ruta de cuenta que devuelve errores con código
    Then: Declara cada una de esas respuestas
    """
    respuestas = fastapi_app.openapi()["paths"][ruta][metodo]["responses"]

    assert codigos <= set(respuestas)
