"""
Un token de acceso se reconoce por lo que es, no por lo que no es (SB-04).

Hasta la re-auditoría del 16 nov 2026 se rechazaba solo el de refresh: cualquier otro
JWT firmado con la misma clave, sin `type` o con otro, valía como acceso si traía
`sub`. Hoy el único otro (el de reautenticación) lleva `aud` y PyJWT ya lo rechaza,
pero el siguiente que se añada no tiene por qué.
"""

import time

import jwt
import pytest

from src.config.settings import settings
from src.shared.infrastructure.security.jwt_handler import JWTTokenService


def _firmado(**payload) -> str:
    """Un JWT firmado con la clave de la API y este payload."""
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_access_token_created_by_the_service_is_accepted():
    """
    Given: Un token de acceso creado por el servicio
    When: Se verifica como acceso
    Then: Vale, con su sujeto
    """
    servicio = JWTTokenService()
    token = servicio.create_access_token({"sub": "u-1", "did": "d-1"})

    payload = servicio.verify_access_token(token)

    assert payload is not None
    assert payload["sub"] == "u-1"


@pytest.mark.parametrize(
    "tipo",
    [None, "refresh", "", "ACCESS", "reauth", "verificacion"],
    ids=["sin-tipo", "refresh", "vacio", "mayusculas", "reauth", "otro"],
)
def test_a_signed_token_that_is_not_access_is_rejected(tipo):
    """
    Given: Un JWT firmado con la clave de la API, con sujeto y dispositivo, cuyo tipo
           no es exactamente "access"
    When: Se verifica como acceso
    Then: No vale
    """
    payload = {"sub": "u-1", "did": "d-1", "exp": int(time.time()) + 600}
    if tipo is not None:
        payload["type"] = tipo

    assert JWTTokenService().verify_access_token(_firmado(**payload)) is None
