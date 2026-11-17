"""
Sentry solo pone usuario con un token de acceso (SB-04, punto gemelo).

`verify_access_token` exige ya `type == "access"`; el middleware que da el usuario a
Sentry decodificaba cualquier JWT firmado con la clave de la API, así que un refresh
token, o uno sin tipo, atribuía a ese usuario los errores de una petición rechazada.
"""

import time

import jwt
import pytest

from src.config.settings import settings
from src.shared.infrastructure.http.sentry_middleware import SentryUserContextMiddleware


def _firmado(**payload) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _middleware() -> SentryUserContextMiddleware:
    return SentryUserContextMiddleware(app=None)


def test_an_access_token_gives_its_payload():
    """
    Given: Un token de acceso firmado por la API
    When: El middleware lo decodifica
    Then: Devuelve su payload, con el usuario
    """
    token = _firmado(sub="u-1", type="access", exp=int(time.time()) + 600)

    assert _middleware()._decode_token(token)["sub"] == "u-1"


@pytest.mark.parametrize("tipo", [None, "refresh", "otro"], ids=["sin-tipo", "refresh", "otro"])
def test_a_signed_token_that_is_not_access_gives_nothing(tipo):
    """
    Given: Un JWT firmado por la API que no es de acceso
    When: El middleware lo decodifica
    Then: No devuelve nada, y Sentry no pone usuario
    """
    payload = {"sub": "u-1", "exp": int(time.time()) + 600}
    if tipo is not None:
        payload["type"] = tipo

    assert _middleware()._decode_token(_firmado(**payload)) is None
