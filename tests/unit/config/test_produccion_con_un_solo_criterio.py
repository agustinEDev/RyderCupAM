"""
Producción se reconoce igual en todas partes (auditoría de la fase 6, B-09).

El arranque trataba como producción todo lo que no dijera expresamente
`development` (falla cerrado), pero las cookies y CORS solo lo que dijera
exactamente `production`. Con un ENVIRONMENT mal escrito (`prod`, vacío) las
cookies salían sin `Secure` y CORS aceptaba `localhost`.

    caso                         | arranque | cookies Secure | CORS sin localhost
    -----------------------------|----------|----------------|-------------------
    P1 production                | prod     | sí             | sí
    P2 development               | desarr.  | no             | no (acepta local)
    P3 prod (mal escrito)        | prod     | sí             | sí
    P4 sin ENVIRONMENT           | prod     | sí             | sí
    P5 " Development " (espacios)| desarr.  | no             | no
"""

import pytest

from src.config import cors_config
from src.shared.infrastructure.security import cookie_handler

ES_PRODUCCION = [
    ("production", True),
    ("development", False),
    ("prod", True),
    (None, True),
    (" Development ", False),
]


@pytest.mark.parametrize(("valor", "esperado"), ES_PRODUCCION)
def test_las_cookies_reconocen_produccion_como_el_arranque(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", valor)

    assert cookie_handler.is_production() is esperado


@pytest.mark.parametrize(("valor", "esperado"), ES_PRODUCCION)
def test_cors_reconoce_produccion_como_el_arranque(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", valor)

    assert cors_config._is_production() is esperado
