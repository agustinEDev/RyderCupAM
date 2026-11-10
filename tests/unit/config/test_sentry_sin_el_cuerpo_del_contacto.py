"""
Sentry no recibe el cuerpo del formulario de contacto (auditoría OWASP, A09): el SDK
adjunta el JSON de la petición a cada error, también con send_default_pii=False, y
ahí van el nombre, el correo y el mensaje de quien escribe.
"""

import pytest

from src.config import sentry_config


def _evento(url: str) -> dict:
    return {
        "request": {
            "url": url,
            "method": "POST",
            "headers": {"User-Agent": "Mozilla/5.0"},
            "data": {"name": "Ana", "email": "ana@example.com", "message": "Hola"},
        }
    }


def test_an_error_of_the_contact_form_goes_without_the_body():
    """
    Given: Un error durante POST /api/v1/support/contact
    When: Pasa por before_send
    Then: Sale sin el cuerpo de la petición
    """
    evento = sentry_config.before_send(
        _evento("https://api.rydercupfriends.com/api/v1/support/contact"), {}
    )

    assert "data" not in evento["request"]


def test_a_contact_form_transaction_goes_without_the_body():
    """Las transacciones también llevan la petición: sin el cuerpo."""
    evento = sentry_config.before_send_transaction(
        _evento("https://api.rydercupfriends.com/api/v1/support/contact"), {}
    )

    assert "data" not in evento["request"]


def test_other_routes_keep_their_body():
    """En las demás rutas no cambia nada (el SDK ya limpia contraseñas y tokens)."""
    evento = sentry_config.before_send(
        _evento("https://api.rydercupfriends.com/api/v1/users/profile"), {}
    )

    assert evento["request"]["data"]["name"] == "Ana"


def test_a_query_string_does_not_hide_the_contact_route():
    """Con ?algo detrás de la ruta, también sale sin el cuerpo."""
    evento = sentry_config.before_send(
        _evento("https://api.rydercupfriends.com/api/v1/support/contact?x=1"), {}
    )

    assert "data" not in evento["request"]


def test_other_routes_keep_their_body_in_transactions_too():
    """En las transacciones de otras rutas tampoco cambia nada."""
    evento = sentry_config.before_send_transaction(
        _evento("https://api.rydercupfriends.com/api/v1/users/profile"), {}
    )

    assert evento["request"]["data"]["name"] == "Ana"


@pytest.mark.parametrize("ruta", ["/api/v1/auth/google", "/api/v1/auth/google/link"])
@pytest.mark.parametrize("hook", ["before_send", "before_send_transaction"])
def test_f8_el_canje_de_google_sale_sin_el_cuerpo(ruta, hook):
    """
    Given: Un error o una transacción de POST /auth/google o /auth/google/link
    When: Pasa por before_send o before_send_transaction
    Then: Sale sin el cuerpo: lleva el código de Google y el code_verifier (F8)
    """
    evento = getattr(sentry_config, hook)(_evento(f"https://api.rydercupfriends.com{ruta}"), {})

    assert "data" not in evento["request"]
