"""
El correo de la sesión que casa invitaciones, en las rutas de competition (F-07).

Toda ruta lo saca de `correo_de_quien_mira`: solo el verificado. Pasar
`current_user.email` a pelo devolvería a una cuenta sin verificar las
invitaciones enviadas a esa dirección (listado, ficha, inscritos, horarios).
"""

import re
from pathlib import Path
from uuid import uuid4

from src.modules.competition.infrastructure.api.v1.correo_de_quien_mira import (
    correo_de_quien_mira,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO

RUTAS = Path(__file__).resolve().parents[6] / "src/modules/competition/infrastructure/api/v1"


def _sesion(verificado: bool) -> UserResponseDTO:
    return UserResponseDTO.model_construct(
        id=uuid4(), email="ana@test.com", email_verified=verificado
    )


def test_con_el_correo_verificado_da_su_correo():
    """
    Given: Una sesión con el correo verificado
    When: Se pide el correo que casa invitaciones
    Then: Es el suyo
    """
    assert correo_de_quien_mira(_sesion(True)) == "ana@test.com"


def test_sin_verificar_no_da_ninguno():
    """
    Given: Una sesión con el correo SIN verificar
    When: Se pide el correo que casa invitaciones
    Then: Ninguno: las invitaciones a esa dirección no existen para ella
    """
    assert correo_de_quien_mira(_sesion(False)) is None


def test_ninguna_ruta_pasa_el_correo_sin_verificar():
    """
    Given: Las rutas de competition
    When: Se buscan usos de `current_user.email`
    Then: No hay ninguno: todas pasan por `correo_de_quien_mira`
    """
    # Menos el propio ayudante, que es quien lo lee
    ficheros = sorted(f for f in RUTAS.glob("*.py") if f.name != "correo_de_quien_mira.py")
    assert ficheros, RUTAS
    a_pelo = [
        f"{f.name}:{n}"
        for f in ficheros
        for n, linea in enumerate(f.read_text().splitlines(), 1)
        if re.search(r"current_user\.email\b(?!_verified)", linea)
    ]
    assert a_pelo == []
