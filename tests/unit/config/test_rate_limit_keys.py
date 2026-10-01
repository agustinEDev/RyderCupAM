"""
Tests unitarios de las claves del rate limit (RyderCupAM#273).

Qué identidad cuenta cada petición. La invariante del ADR-038 no cambia: ninguna
cabecera que escriba el cliente elige el contador. Lo nuevo es que el tráfico con
sesión cuenta por usuario, y el usuario sale de un JWT cuya firma se verifica: un
token inventado no elige contador, cae en el de red.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

from src.config import rate_limit
from src.config.rate_limit import (
    count_or_refuse,
    email_rate_limit_key,
    get_client_identifier,
    get_rate_limit_key,
    limiter,
    record_failed_login,
    refuse_if_failed_logins_exhausted,
)
from src.config.settings import settings
from src.shared.infrastructure.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
)

PEER = "10.1.2.3"


def _request(cookie_token: str | None = None, bearer_token: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie_token:
        headers.append((b"cookie", f"access_token={cookie_token}".encode()))
    if bearer_token:
        headers.append((b"authorization", f"Bearer {bearer_token}".encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "query_string": b"",
        "headers": headers,
        "client": (PEER, 12345),
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _production(monkeypatch):
    """En producción la clave de red es solo la IP del peer: sin escape de tests."""
    monkeypatch.setenv("ENVIRONMENT", "production")


def test_valid_access_token_in_cookie_keys_on_the_user():
    """
    Given: Un access token válido en la cookie
    When: Se calcula la clave
    Then: Es la del usuario del token
    """
    user_id = str(uuid4())

    key = get_rate_limit_key(_request(cookie_token=create_access_token({"sub": user_id})))

    assert key == f"user:{user_id}"


def test_valid_access_token_in_bearer_header_keys_on_the_user():
    """
    Given: Un access token válido solo en la cabecera Authorization
    When: Se calcula la clave
    Then: Es la del usuario del token
    """
    user_id = str(uuid4())

    key = get_rate_limit_key(_request(bearer_token=create_access_token({"sub": user_id})))

    assert key == f"user:{user_id}"


def test_cookie_wins_over_bearer_header_like_get_current_user():
    """
    Given: La cookie de A y la cabecera de B
    When: Se calcula la clave
    Then: Cuenta A, la misma prioridad con la que get_current_user autentica
    """
    user_a, user_b = str(uuid4()), str(uuid4())

    key = get_rate_limit_key(
        _request(
            cookie_token=create_access_token({"sub": user_a}),
            bearer_token=create_access_token({"sub": user_b}),
        )
    )

    assert key == f"user:{user_a}"


def test_forged_token_does_not_choose_the_bucket():
    """
    Given: Un token firmado con otra clave y un sub elegido por el atacante
    When: Se calcula la clave
    Then: Cae en la de red; si no, rotar el sub daría un contador nuevo por petición
    """
    forged = jwt.encode(
        {"sub": "chosen-by-attacker", "type": "access"}, "not-the-secret", algorithm="HS256"
    )

    key = get_rate_limit_key(_request(cookie_token=forged))

    assert key == PEER


def test_expired_token_keys_on_the_network():
    """
    Given: Un access token caducado
    When: Se calcula la clave
    Then: Cae en la de red
    """
    # A mano y en UTC: create_access_token usa datetime.now() sin zona, y fuera de
    # UTC un "-1 s" no está caducado
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    assert get_rate_limit_key(_request(cookie_token=expired)) == PEER


def test_refresh_token_is_not_an_access_token_for_the_key():
    """
    Given: Un refresh token donde va el access token
    When: Se calcula la clave
    Then: Cae en la de red, como lo rechaza get_current_user
    """
    refresh = create_refresh_token({"sub": str(uuid4())})

    assert get_rate_limit_key(_request(bearer_token=refresh)) == PEER


def test_token_without_subject_keys_on_the_network():
    """
    Given: Un access token válido sin sub
    When: Se calcula la clave
    Then: Cae en la de red
    """
    no_sub = jwt.encode({"type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    assert get_rate_limit_key(_request(cookie_token=no_sub)) == PEER


def test_no_token_keys_on_the_network():
    """
    Given: Una petición sin token
    When: Se calcula la clave
    Then: Es la de red, la misma que get_client_identifier
    """
    request = _request()

    assert get_rate_limit_key(request) == get_client_identifier(request) == PEER


def test_email_key_is_normalised_and_does_not_contain_the_email():
    """
    Given: El mismo email escrito con mayúsculas y espacios
    When: Se calcula su clave
    Then: Coincide con la del email normalizado y no lleva el email en claro
    """
    key = email_rate_limit_key("  Pepe.Perez@Example.COM ")

    assert key == email_rate_limit_key("pepe.perez@example.com")
    assert "pepe" not in key.lower()
    assert key != email_rate_limit_key("otro@example.com")


def test_manual_counters_respect_a_disabled_limiter(monkeypatch):
    """
    Given: El limiter apagado (limiter.enabled = False), como lo apaga slowapi
    When: Se cuenta por encima del tope con los contadores que no son decorador
    Then: No rechazan nada, igual que los decoradores con el limiter apagado
    """
    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr(rate_limit, "FAILED_LOGINS_LIMIT", "1/minute")
    request = _request()

    for _ in range(3):
        count_or_refuse("1/minute", "test-disabled", "same-key")
        record_failed_login(request)
    refuse_if_failed_logins_exhausted(request)


def test_manual_counters_refuse_over_the_limit_when_enabled(monkeypatch):
    """
    Given: El limiter encendido y un tope de 1/minuto
    When: Se cuenta dos veces la misma clave, y se registra un fallo de login
    Then: La segunda cuenta y el siguiente login dan 429 (contraprueba del anterior)
    """
    monkeypatch.setattr(rate_limit, "FAILED_LOGINS_LIMIT", "1/minute")
    request = _request()
    limiter.reset()

    count_or_refuse("1/minute", "test-enabled", "same-key")
    with pytest.raises(RateLimitExceeded):
        count_or_refuse("1/minute", "test-enabled", "same-key")

    record_failed_login(request)
    with pytest.raises(RateLimitExceeded):
        refuse_if_failed_logins_exhausted(request)
    limiter.reset()
