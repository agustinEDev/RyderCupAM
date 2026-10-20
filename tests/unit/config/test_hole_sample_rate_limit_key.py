"""
La clave del límite de mandar muestras de hoyo (BE #532, revisión del 16 oct 2026).

slowapi escribe la clave en el log cuando alguien pasa del límite. En las demás
rutas con sesión es `user:<uuid>`; en la de muestras, que son anónimas, el log
no puede decir quién: la clave sigue siendo una por usuario, pero es un HMAC
del id con el secreto de la app, recortado.

| Caso                                          | Resultado                                   |
|-----------------------------------------------|---------------------------------------------|
| Con sesión                                    | `sample:` + hash, sin el uuid               |
| El mismo usuario dos veces                    | La misma clave (sigue contando por usuario) |
| Dos usuarios                                  | Claves distintas                            |
| Sin sesión o con un token inventado           | La de red, como las demás                   |
| La ruta POST de muestras                      | Usa esta clave                              |
"""

from uuid import uuid4

import pytest
from starlette.requests import Request

from src.config.rate_limit import (
    get_client_identifier,
    get_hole_sample_rate_limit_key,
    limiter,
)
from src.shared.infrastructure.security.jwt_handler import create_access_token

PEER = "10.1.2.3"


def _request(token: str | None = None) -> Request:
    headers = [(b"cookie", f"access_token={token}".encode())] if token else []
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "query_string": b"",
            "headers": headers,
            "client": (PEER, 12345),
        }
    )


@pytest.fixture(autouse=True)
def _production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")


def _key_of(user_id: str) -> str:
    return get_hole_sample_rate_limit_key(_request(create_access_token({"sub": user_id})))


def test_with_a_session_the_key_does_not_reveal_the_user():
    """
    GIVEN: Un access token válido
    WHEN: Se calcula la clave de las muestras
    THEN: Empieza por `sample:` y no lleva el uuid (ni entero ni en sus trozos)
    """
    user_id = str(uuid4())

    key = _key_of(user_id)

    assert key.startswith("sample:")
    assert user_id not in key
    assert user_id.replace("-", "") not in key
    assert not any(part in key for part in user_id.split("-") if len(part) >= 8)


def test_the_same_user_keeps_the_same_key_and_two_users_differ():
    """
    GIVEN: Dos usuarios
    WHEN: Se calcula la clave dos veces para el primero y una para el segundo
    THEN: La del primero no cambia, y la del segundo es otra
    """
    one, other = str(uuid4()), str(uuid4())

    assert _key_of(one) == _key_of(one)
    assert _key_of(one) != _key_of(other)


@pytest.mark.parametrize("token", [None, "no-es-un-jwt"])
def test_without_a_valid_session_it_is_the_network(token):
    """
    GIVEN: Sin token, o con uno inventado
    WHEN: Se calcula la clave
    THEN: Es la de red
    """
    request = _request(token)

    assert get_hole_sample_rate_limit_key(request) == get_client_identifier(request)


def test_the_samples_route_uses_this_key():
    """
    GIVEN: El límite de POST .../hole-map/samples/{hole}
    WHEN: Se mira su clave
    THEN: Es la de las muestras
    """
    name = "src.modules.golf_course.infrastructure.api.v1.hole_map_routes.submit_hole_sample"

    (limit,) = limiter._route_limits[name]

    assert limit.key_func is get_hole_sample_rate_limit_key
