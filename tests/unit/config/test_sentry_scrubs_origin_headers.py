"""
Ni el secreto de Cloudflare ni la IP del usuario viajan a Sentry (BE #466).

`send_default_pii=False` solo quita las cabeceras sensibles que el SDK conoce
(Authorization, Cookie, X-Forwarded-For...). `X-Origin-Verify` lleva el secreto
que hace creíble la IP de Cloudflare, y `CF-Connecting-IP` y `True-Client-IP`
llevan la IP del usuario: sin quitarlas, irían en cada error y en cada
transacción, la misma clase de fuga que la clave de Mailgun de julio de 2026.
"""

from unittest.mock import patch

import pytest

from src.config import sentry_config

DSN = "https://public@o0.ingest.sentry.io/0"


def _evento(**cabeceras: str) -> dict:
    """Un evento con la petición y estas cabeceras."""
    return {
        "request": {
            "url": "https://api.rydercupfriends.com/api/v1/users/profile",
            "method": "PATCH",
            "headers": {"User-Agent": "Mozilla/5.0", **cabeceras},
        }
    }


@pytest.mark.parametrize(
    "nombre", ["X-Origin-Verify", "x-origin-verify", "CF-Connecting-IP", "True-Client-IP"]
)
def test_before_send_removes_origin_secret_and_client_ip_headers(nombre):
    """
    Given: Un error con una cabecera del secreto o de la IP del usuario, en cualquier grafía
    When: Pasa por before_send
    Then: Sale sin ella, y las demás cabeceras se quedan
    """
    evento = sentry_config.before_send(_evento(**{nombre: "valor"}), {})

    assert nombre not in evento["request"]["headers"]
    assert evento["request"]["headers"]["User-Agent"] == "Mozilla/5.0"


def test_before_send_transaction_removes_origin_secret_and_client_ip_headers():
    """
    Given: Una transacción con el secreto y la IP del usuario
    When: Pasa por before_send_transaction
    Then: Sale sin ninguna de las dos
    """
    evento = sentry_config.before_send_transaction(
        _evento(**{"X-Origin-Verify": "secreto", "CF-Connecting-IP": "203.0.113.7"}), {}
    )

    assert set(evento["request"]["headers"]) == {"User-Agent"}


def test_scrubbing_tolerates_events_without_request_or_headers():
    """
    Given: Eventos sin petición, o con la petición sin cabeceras
    When: Pasan por before_send y before_send_transaction
    Then: Salen tal cual, sin lanzar
    """
    for evento in ({"message": "x"}, {"request": {"url": "https://x/y", "method": "GET"}}):
        assert sentry_config.before_send(dict(evento), {}) is not None
        assert sentry_config.before_send_transaction(dict(evento), {}) is not None


def test_init_sentry_registers_both_scrubbing_hooks(monkeypatch):
    """
    Given: Sentry con DSN
    When: Se inicializa
    Then: Registra before_send y before_send_transaction: sin el segundo, las transacciones llevarían el secreto
    """
    monkeypatch.setattr(sentry_config.settings, "SENTRY_DSN", DSN)
    with patch.object(sentry_config.sentry_sdk, "init") as init:
        sentry_config.init_sentry()

    kwargs = init.call_args.kwargs
    assert kwargs["before_send"] is sentry_config.before_send
    assert kwargs["before_send_transaction"] is sentry_config.before_send_transaction
