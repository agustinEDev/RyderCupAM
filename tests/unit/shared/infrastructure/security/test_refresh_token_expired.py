"""
Si un refresh token es de esta API, con la firma buena, y ha caducado (FE #1042).

Separa el final normal de una sesión (REFRESH_TOKEN_EXPIRED) de un token inválido
(REFRESH_TOKEN_INVALID): el front avisa a Sentry solo de lo segundo.
"""

import time

import jwt
import pytest

from src.config.settings import settings
from src.shared.infrastructure.security.jwt_handler import JWTTokenService


def _firmado(clave: str = settings.SECRET_KEY, **payload) -> str:
    """Un JWT firmado con esta clave y este payload."""
    return jwt.encode(payload, clave, algorithm=settings.ALGORITHM)


def test_refresh_token_expired_with_good_signature_is_true():
    """
    Given: Un refresh token de esta API, caducado hace un minuto
    When: Se pregunta si está caducado
    Then: Sí
    """
    token = _firmado(sub="u", type="refresh", exp=int(time.time()) - 60)

    assert JWTTokenService().refresh_token_expired(token) is True


@pytest.mark.parametrize(
    "hazlo",
    [
        lambda: _firmado(sub="u", type="refresh", exp=int(time.time()) + 600),
        lambda: _firmado(sub="u", type="access", exp=int(time.time()) - 60),
        lambda: _firmado(
            clave="otra-clave-de-32-bytes-como-minimo!!", sub="u", type="refresh", exp=1
        ),
        lambda: _firmado(sub="u", type="refresh"),
        lambda: "basura",
    ],
    ids=["vigente", "de-acceso", "otra-firma", "sin-exp", "basura"],
)
def test_refresh_token_expired_is_false_for_anything_else(hazlo):
    """
    Given: Un refresh vigente, uno de acceso caducado, otra firma, sin exp o basura
    When: Se pregunta si es un refresh caducado
    Then: No: o sigue valiendo o es inválido. Se firman al ejecutar el test, no al
          recogerlo: un «vigente» de 10 minutos no puede caducar en una cola larga
    """
    assert JWTTokenService().refresh_token_expired(hazlo()) is False
