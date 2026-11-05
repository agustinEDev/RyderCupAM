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


def test_1_uno_valido_da_su_sub():
    """Caso 1 de la tabla de la cabecera: uno valido da su sub."""
    assert subject_ignoring_expiry(JWTTokenService().create_access_token({"sub": SUB})) == SUB


def test_2_caducado_con_la_firma_buena_tambien():
    """Caso 2 de la tabla de la cabecera: caducado con la firma buena tambien."""
    assert subject_ignoring_expiry(_firmado({"sub": SUB, "exp": int(time.time()) - 3600})) == SUB


def test_3_con_otra_clave_no():
    """Caso 3 de la tabla de la cabecera: con otra clave no."""
    assert (
        subject_ignoring_expiry(_firmado({"sub": SUB}, clave="otra-clave-de-32-bytes-o-mas-xxxxx"))
        is None
    )


def test_4_alg_none_no():
    """Caso 4 de la tabla de la cabecera: alg none no."""
    sin_firma = jwt.encode({"sub": SUB}, key=None, algorithm="none")

    assert subject_ignoring_expiry(sin_firma) is None


@pytest.mark.parametrize("payload", [{}, {"sub": 42}, {"sub": ""}])
def test_5_sin_sub_de_texto_no(payload):
    """Caso 5 de la tabla de la cabecera: sin sub de texto no."""
    assert subject_ignoring_expiry(_firmado(payload)) is None


@pytest.mark.parametrize("basura", ["", "abc", "a.b.c"])
def test_6_basura_no(basura):
    """Caso 6 de la tabla de la cabecera: basura no."""
    assert subject_ignoring_expiry(basura) is None
