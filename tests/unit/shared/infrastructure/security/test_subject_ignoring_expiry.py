"""
`subject_ignoring_expiry`: de quién es un JWT de esta API, aunque haya caducado (BE #724).

  #  token                                  | resultado
  ---|-------------------------------------|-----------------
  1  de acceso válido                       | su `sub`
  2  caducado, con la firma buena           | su `sub`
  3  firmado con otra clave                 | None
  4  `alg: none`                            | None
  5  sin `sub`, o `sub` que no es texto     | None
  6  basura                                 | None
"""

import time

import jwt
import pytest

from src.config.settings import settings
from src.shared.infrastructure.security.jwt_handler import JWTTokenService, subject_ignoring_expiry

SUB = "11111111-1111-1111-1111-111111111111"


def _firmado(payload, clave=None):
    """Ayudante del test: firmado."""
    return jwt.encode(payload, clave or settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_subject_ignoring_expiry_valid_token_returns_sub():
    """
    Given: Un JWT válido
    When: Se lee su usuario
    Then: Devuelve su sub
    """
    assert subject_ignoring_expiry(JWTTokenService().create_access_token({"sub": SUB})) == SUB


def test_subject_ignoring_expiry_expired_token_returns_sub():
    """
    Given: Un JWT caducado con la firma buena
    When: Se lee su usuario
    Then: Devuelve su sub
    """
    assert subject_ignoring_expiry(_firmado({"sub": SUB, "exp": int(time.time()) - 3600})) == SUB


def test_subject_ignoring_expiry_other_key_returns_none():
    """
    Given: Un JWT firmado con otra clave
    When: Se lee su usuario
    Then: None
    """
    assert (
        subject_ignoring_expiry(_firmado({"sub": SUB}, clave="otra-clave-de-32-bytes-o-mas-xxxxx"))
        is None
    )


def test_subject_ignoring_expiry_alg_none_returns_none():
    """
    Given: Un JWT con alg none
    When: Se lee su usuario
    Then: None
    """
    sin_firma = jwt.encode({"sub": SUB}, key=None, algorithm="none")

    assert subject_ignoring_expiry(sin_firma) is None


@pytest.mark.parametrize("payload", [{}, {"sub": 42}, {"sub": ""}])
def test_subject_ignoring_expiry_without_string_sub_returns_none(payload):
    """
    Given: Un JWT sin sub de texto
    When: Se lee su usuario
    Then: None
    """
    assert subject_ignoring_expiry(_firmado(payload)) is None


@pytest.mark.parametrize("basura", ["", "abc", "a.b.c"])
def test_subject_ignoring_expiry_garbage_returns_none(basura):
    """
    Given: Algo que no es un JWT
    When: Se lee su usuario
    Then: None
    """
    assert subject_ignoring_expiry(basura) is None
