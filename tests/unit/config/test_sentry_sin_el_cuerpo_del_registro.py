"""
Sentry no recibe el cuerpo del registro (fase 3, B-4): nombre, correo y contraseña.

El GET obsoleto `/auth/validate-reset-token/{token}`, que llevaba el token en la URL y
por eso salía tachado, se quitó en la 2.58.0, y con él su tachado.
"""

from src.config import sentry_config


def _evento(url: str, **mas) -> dict:
    return {"request": {"url": url, "method": "POST", "data": {"x": 1}}, **mas}


def test_b4_the_register_body_does_not_go_to_sentry():
    """
    Given: Un error durante POST /api/v1/auth/register
    When: Pasa por before_send y por before_send_transaction
    Then: Sin el cuerpo (nombre, correo y contraseña)
    """
    url = "https://api.rydercupfriends.com/api/v1/auth/register"

    assert "data" not in sentry_config.before_send(_evento(url), {})["request"]
    assert "data" not in sentry_config.before_send_transaction(_evento(url), {})["request"]


def test_b4_other_urls_keep_their_body():
    """Otra ruta no cambia: ni la URL ni el cuerpo."""
    url = "https://api.rydercupfriends.com/api/v1/users/profile"

    evento = sentry_config.before_send(_evento(url), {})

    assert evento["request"] == {"url": url, "method": "POST", "data": {"x": 1}}
