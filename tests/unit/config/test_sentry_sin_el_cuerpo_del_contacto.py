"""
Sentry no recibe el cuerpo del formulario de contacto (auditoría OWASP, A09): el SDK
adjunta el JSON de la petición a cada error, también con send_default_pii=False, y
ahí van el nombre, el correo y el mensaje de quien escribe.
"""

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
