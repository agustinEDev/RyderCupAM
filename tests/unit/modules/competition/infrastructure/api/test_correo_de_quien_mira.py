"""
El correo de la sesión que casa invitaciones, en las rutas de competition (F-07).

Toda ruta lo saca de `correo_de_quien_mira`: solo el verificado. Pasar
`current_user.email` a pelo devolvería a una cuenta sin verificar las
invitaciones enviadas a esa dirección (listado, ficha, inscritos, horarios).
"""

import ast
from pathlib import Path
from uuid import uuid4

from src.modules.competition.infrastructure.api.v1.correo_de_quien_mira import (
    correo_de_quien_mira,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO

RUTAS = Path(__file__).resolve().parents[6] / "src/modules/competition/infrastructure/api/v1"


def _sesion(verificado: bool) -> UserResponseDTO:
    """Una sesión con el correo verificado o sin verificar."""
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


def _correos_de_la_sesion(codigo: str) -> list[int]:
    """
    Las líneas donde se lee `.email` de un parámetro anotado como `UserResponseDTO`
    (la sesión), se llame como se llame: `current_user`, `yo`, `usuario`...
    """
    lineas = []
    for funcion in ast.walk(ast.parse(codigo)):
        if not isinstance(funcion, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        argumentos = [*funcion.args.posonlyargs, *funcion.args.args, *funcion.args.kwonlyargs]
        sesiones = {
            a.arg
            for a in argumentos
            if a.annotation is not None and "UserResponseDTO" in ast.unparse(a.annotation)
        }
        lineas += [
            nodo.lineno
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Attribute)
            and nodo.attr == "email"
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id in sesiones
        ]
    return lineas


def test_ninguna_ruta_lee_el_correo_de_la_sesion():
    """
    Given: Las rutas de competition
    When: Se busca, por el tipo y no por el nombre, dónde se lee el correo de la sesión
    Then: En ningún sitio: todas pasan por `correo_de_quien_mira`
    """
    # Menos el propio ayudante, que es quien lo lee
    ficheros = sorted(f for f in RUTAS.glob("*.py") if f.name != "correo_de_quien_mira.py")
    assert ficheros, RUTAS
    a_pelo = [f"{f.name}:{n}" for f in ficheros for n in _correos_de_la_sesion(f.read_text())]
    assert a_pelo == []


def test_el_vigia_encuentra_el_correo_con_cualquier_nombre():
    """
    Given: Una ruta que lee el correo de la sesión con otro nombre de variable
    When: Pasa el vigía
    Then: La encuentra
    """
    codigo = (
        "async def ruta(yo: UserResponseDTO = Depends(get_current_user)):\n"
        "    return await caso(email=yo.email)\n"
    )

    assert _correos_de_la_sesion(codigo) == [2]
