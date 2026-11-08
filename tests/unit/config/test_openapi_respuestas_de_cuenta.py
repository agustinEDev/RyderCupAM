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
        ("/api/v1/users/security", "patch", {"400", "401", "403", "404", "409", "429"}),
        ("/api/v1/auth/login", "post", {"401", "403", "423", "429"}),
        ("/api/v1/auth/google/unlink", "delete", {"400", "403"}),
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


@pytest.mark.parametrize(
    ("ruta", "metodo", "estado", "dice", "no_dice"),
    [
        # Los códigos que la respuesta lleva de verdad, nombrados
        ("/api/v1/users/security", "patch", "401", "CURRENT_PASSWORD_INCORRECT", None),
        ("/api/v1/users/security", "patch", "409", "EMAIL_ALREADY_IN_USE", None),
        ("/api/v1/users/security", "patch", "403", "TERMS_NOT_ACCEPTED", None),
        # El 429 del login es el de cualquier límite, sin `error_code` (/code-review)
        ("/api/v1/auth/login", "post", "429", "429", "error_code"),
    ],
)
def test_the_documented_response_names_only_the_codes_it_carries(
    ruta, metodo, estado, dice, no_dice
):
    """
    Given: El esquema OpenAPI de la app
    When: Se lee la descripción de una respuesta documentada
    Then: Nombra el `error_code` que lleva, y no promete uno que no lleva
    """
    descripcion = fastapi_app.openapi()["paths"][ruta][metodo]["responses"][estado]["description"]

    assert dice in descripcion or dice == estado
    if no_dice:
        assert no_dice not in descripcion
