"""
La caducidad de los JWT se calcula en UTC (BE #727).

`datetime.now()` sin zona es la hora local, y PyJWT convierte una fecha sin zona
como si fuera UTC: en una máquina a UTC+9 un token de 15 minutos nacía con nueve
horas y cuarto de vida; a UTC-5, ya caducado. Producción corre en UTC y no se
notaba; en los equipos de desarrollo y en los tests, sí.
"""

import os
import time
from datetime import timedelta

import jwt
import pytest

from src.config.settings import settings
from src.shared.infrastructure.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
)

MARGEN_S = 5


@pytest.fixture(params=["Asia/Tokyo", "America/New_York"])
def zona_que_no_es_utc(request):
    """El proceso en una zona por delante o por detrás de UTC; al acabar, la de antes."""
    antes = os.environ.get("TZ")
    os.environ["TZ"] = request.param
    time.tzset()
    yield request.param
    if antes is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = antes
    time.tzset()


def _vida_en_segundos(token: str) -> float:
    """Cuánto le queda al token, leyendo su exp sin validarlo."""
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"verify_exp": False},
    )
    return payload["exp"] - time.time()


def test_access_token_default_lifetime_outside_utc_is_its_configured_minutes(zona_que_no_es_utc):
    """
    Given: El proceso en una zona que no es UTC
    When: Se crea un access token con la duración por defecto
    Then: Vive ACCESS_TOKEN_EXPIRE_MINUTES, ni una hora más ni ya caducado
    """
    esperado = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    vida = _vida_en_segundos(create_access_token({"sub": "u"}))

    assert abs(vida - esperado) < MARGEN_S


def test_access_token_custom_lifetime_outside_utc_is_that_delta(zona_que_no_es_utc):
    """
    Given: El proceso en una zona que no es UTC
    When: Se crea un access token de 5 minutos
    Then: Vive 5 minutos
    """
    vida = _vida_en_segundos(create_access_token({"sub": "u"}, timedelta(minutes=5)))

    assert abs(vida - 300) < MARGEN_S


def test_refresh_token_default_lifetime_outside_utc_is_its_configured_days(zona_que_no_es_utc):
    """
    Given: El proceso en una zona que no es UTC
    When: Se crea un refresh token con la duración por defecto
    Then: Vive REFRESH_TOKEN_EXPIRE_DAYS
    """
    esperado = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400

    vida = _vida_en_segundos(create_refresh_token({"sub": "u"}))

    assert abs(vida - esperado) < MARGEN_S


def test_refresh_token_custom_lifetime_outside_utc_is_that_delta(zona_que_no_es_utc):
    """
    Given: El proceso en una zona que no es UTC
    When: Se crea un refresh token de 1 hora
    Then: Vive 1 hora
    """
    vida = _vida_en_segundos(create_refresh_token({"sub": "u"}, timedelta(hours=1)))

    assert abs(vida - 3600) < MARGEN_S
