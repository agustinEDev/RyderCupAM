"""
El adaptador que manda el mensaje de contacto por Mailgun (C1, C5).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.modules.support.infrastructure.services.mailgun_contact_mailer import (
    MailgunContactMailer,
)

MODULO = "src.modules.support.infrastructure.services.mailgun_contact_mailer"


def _cliente(status_code=200, error=None):
    cliente = AsyncMock()
    if error:
        cliente.post.side_effect = error
    else:
        cliente.post.return_value = MagicMock(status_code=status_code)
    cliente.__aenter__ = AsyncMock(return_value=cliente)
    cliente.__aexit__ = AsyncMock(return_value=None)
    return cliente


def _mailer():
    return MailgunContactMailer(
        api_key="clave-de-prueba",
        api_url="https://api.eu.mailgun.net/v3",
        domain="rydercupfriends.com",
        from_email="Ryder Cup Friends <noreply@rydercupfriends.com>",
        to_email="admin@rydercupfriends.com",
    )


async def test_it_posts_to_admin_with_reply_to():
    """
    Given: Mailgun responde 200
    When: Se manda un mensaje
    Then: True; a admin@, desde noreply@, con Reply-To de quien escribe y solo texto
    """
    cliente = _cliente()
    with patch(f"{MODULO}.httpx.AsyncClient", return_value=cliente) as cliente_clase:
        enviado = await _mailer().send(
            subject="[Contacto · Pregunta] Hola", text="Cuerpo", reply_to="ana@example.com"
        )

    assert enviado is True
    # Con tiempo máximo: un Mailgun colgado no retiene la petición sin fin
    assert cliente_clase.call_args.kwargs["timeout"] == 10.0
    url = cliente.post.call_args.args[0]
    kw = cliente.post.call_args.kwargs
    assert url == "https://api.eu.mailgun.net/v3/rydercupfriends.com/messages"
    assert kw["auth"] == ("api", "clave-de-prueba")
    assert kw["data"] == {
        "from": "Ryder Cup Friends <noreply@rydercupfriends.com>",
        "to": "admin@rydercupfriends.com",
        "subject": "[Contacto · Pregunta] Hola",
        "text": "Cuerpo",
        "h:Reply-To": "ana@example.com",
    }


@pytest.mark.parametrize("status_code", [400, 401, 500])
async def test_a_refused_message_is_false(status_code):
    """Mailgun no lo acepta: False, para que el caso de uso devuelva el hueco."""
    with patch(f"{MODULO}.httpx.AsyncClient", return_value=_cliente(status_code)):
        assert await _mailer().send(subject="s", text="t", reply_to="a@example.com") is False


async def test_a_network_error_is_false():
    """Sin red con Mailgun: False, sin excepción."""
    error = httpx.ConnectError("sin red")
    with patch(f"{MODULO}.httpx.AsyncClient", return_value=_cliente(error=error)):
        assert await _mailer().send(subject="s", text="t", reply_to="a@example.com") is False


async def test_without_api_key_nothing_is_sent():
    """Sin clave de Mailgun: False y ni se intenta."""
    mailer = _mailer()
    mailer._api_key = ""
    with patch(f"{MODULO}.httpx.AsyncClient") as cliente:
        assert await mailer.send(subject="s", text="t", reply_to="a@example.com") is False
    cliente.assert_not_called()


async def test_a_non_ascii_address_goes_without_reply_to():
    """
    Given: Un correo con tildes (EmailStr lo acepta; en una cabecera no se puede codificar)
    When: Se manda
    Then: Sin h:Reply-To, para que Mailgun no lo rechace; el correo ya va en el cuerpo
    """
    cliente = _cliente()
    with patch(f"{MODULO}.httpx.AsyncClient", return_value=cliente):
        assert await _mailer().send(subject="s", text="t", reply_to="josé@example.com") is True

    assert "h:Reply-To" not in cliente.post.call_args.kwargs["data"]


async def test_an_unexpected_error_is_false():
    """Un error que no es de red (una URL mal puesta): False, sin excepción."""
    error = httpx.InvalidURL("mal")
    with patch(f"{MODULO}.httpx.AsyncClient", return_value=_cliente(error=error)):
        assert await _mailer().send(subject="s", text="t", reply_to="a@example.com") is False
