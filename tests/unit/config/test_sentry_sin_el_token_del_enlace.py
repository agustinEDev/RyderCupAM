"""
Sentry no recibe el token del enlace de restablecer ni el cuerpo del registro (fase 3,
B-4).

El GET obsoleto `/auth/validate-reset-token/{token}` lleva el token en la URL: mientras
exista (se quita en la 2.58.0), la URL de los errores y de las transacciones sale con
el token tachado. El cuerpo del registro lleva nombre, correo y contraseña.
"""

from src.config import sentry_config

TOKEN = "N8OOmyeO4jYrCqxfWhjsogGsR_HK8QcJeV25oqtKt30"
URL = f"https://api.rydercupfriends.com/api/v1/auth/validate-reset-token/{TOKEN}"


def _evento(url: str, **mas) -> dict:
    return {"request": {"url": url, "method": "GET", "data": {"x": 1}}, **mas}


def test_b4_an_error_of_the_old_get_goes_without_the_token():
    """
    Given: Un error durante el GET con el token en la URL
    When: Pasa por before_send
    Then: La URL sale con el token tachado
    """
    evento = sentry_config.before_send(_evento(URL), {})

    assert TOKEN not in str(evento)
    assert evento["request"]["url"].endswith("/api/v1/auth/validate-reset-token/[Filtered]")


def test_b4_a_transaction_of_the_old_get_goes_without_the_token():
    """
    Given: La transacción del GET, con la URL y el nombre con el token
    When: Pasa por before_send_transaction
    Then: Ni la URL ni el nombre llevan el token
    """
    evento = sentry_config.before_send_transaction(_evento(URL, transaction=URL), {})

    assert TOKEN not in str(evento)


def test_b4_a_query_string_after_the_token_does_not_hide_it():
    """Con ?algo detrás, el token también sale tachado."""
    evento = sentry_config.before_send(_evento(f"{URL}?x=1"), {})

    assert TOKEN not in str(evento)


def test_b4_other_urls_are_left_alone():
    """Otra ruta no cambia."""
    url = "https://api.rydercupfriends.com/api/v1/users/profile"

    evento = sentry_config.before_send(_evento(url), {})

    assert evento["request"]["url"] == url


def test_b4_the_register_body_does_not_go_to_sentry():
    """
    Given: Un error durante POST /api/v1/auth/register
    When: Pasa por before_send y por before_send_transaction
    Then: Sin el cuerpo (nombre, correo y contraseña)
    """
    url = "https://api.rydercupfriends.com/api/v1/auth/register"

    assert "data" not in sentry_config.before_send(_evento(url), {})["request"]
    assert "data" not in sentry_config.before_send_transaction(_evento(url), {})["request"]


def test_b4_the_breadcrumbs_go_without_the_token():
    """
    Given: Un error con migas que llevan la URL del GET (la línea de acceso de uvicorn,
           una petición HTTP) en el mensaje y en los datos
    When: Pasa por before_send y por before_send_transaction
    Then: Ninguna miga lleva el token
    """
    migas = {
        "values": [
            {"category": "uvicorn.access", "message": f'"GET {URL} HTTP/1.1" 200'},
            {"category": "httplib", "data": {"url": URL, "method": "GET"}},
        ]
    }
    lista = [{"message": f"GET {URL}"}]

    error = sentry_config.before_send(_evento(URL, breadcrumbs=migas), {})
    transaccion = sentry_config.before_send_transaction(_evento(URL, breadcrumbs=lista), {})

    assert TOKEN not in str(error) and TOKEN not in str(transaccion)
