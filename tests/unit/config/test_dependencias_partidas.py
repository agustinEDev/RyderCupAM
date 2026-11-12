"""
`src.config.dependencies` partido en un módulo por contexto, sin cambiar nada (fase 5).

Era un fichero de 3.769 líneas con los 255 proveedores. Ahora es un paquete: `comun` (sesión,
unidades de trabajo, usuario actual, correo, log de seguridad) y un módulo por contexto que
solo importa de `comun`. El paquete reexporta todo, así que `from src.config.dependencies
import get_x` sigue valiendo y FastAPI ve las mismas funciones (D1-D6).
"""

import ast
import importlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import dependencies
from tests.unit.config.nombres_de_las_dependencias import NOMBRES_DE_ANTES

RAIZ = Path(__file__).resolve().parents[3]
PAQUETE = RAIZ / "src/config/dependencies"
SUBMODULOS = (
    "comun",
    "usuarios",
    "competicion",
    "competicion_juego",
    "campos",
    "partida_rapida",
    "social",
    "soporte",
)
TOPE_DE_LINEAS = 900


def _definidos(nombre_del_submodulo: str) -> set[str]:
    """Lo que un submódulo define: funciones, clases y asignaciones de módulo."""
    arbol = ast.parse((PAQUETE / f"{nombre_del_submodulo}.py").read_text())
    nombres = set()
    for nodo in arbol.body:
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            nombres.add(nodo.name)
        elif isinstance(nodo, ast.Assign):
            nombres |= {t.id for t in nodo.targets if isinstance(t, ast.Name)}
        elif isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
            nombres.add(nodo.target.id)
    return nombres


def test_d1_el_paquete_expone_todo_lo_de_antes():
    """Given los nombres de antes, When se buscan en el paquete, Then están todos."""
    faltan = sorted(n for n in NOMBRES_DE_ANTES if not hasattr(dependencies, n))
    assert faltan == []


def test_d1_no_aparece_ningun_proveedor_nuevo():
    """Given los submódulos, When se juntan sus definiciones, Then no hay nada que no estuviera antes."""
    nuevos = set().union(*(_definidos(m) for m in SUBMODULOS)) - set(NOMBRES_DE_ANTES)
    assert nuevos <= {"_lanzador", "T"}


def test_d2_cada_nombre_se_define_en_un_solo_submodulo():
    """Given los submódulos, When se cruzan sus definiciones, Then ningún nombre está en dos."""
    vistos: dict[str, str] = {}
    repetidos = []
    for modulo in SUBMODULOS:
        for nombre in _definidos(modulo):
            if nombre in vistos:
                repetidos.append((nombre, vistos[nombre], modulo))
            vistos[nombre] = modulo
    assert repetidos == []


@pytest.mark.parametrize("modulo", SUBMODULOS)
def test_d2_lo_reexportado_es_el_mismo_objeto(modulo):
    """Given un submódulo, When se compara con el paquete, Then cada proveedor es el mismo objeto."""
    sub = importlib.import_module(f"src.config.dependencies.{modulo}")
    distintos = [
        n
        for n in _definidos(modulo) - {"_lanzador", "T"}
        if getattr(dependencies, n) is not getattr(sub, n)
    ]
    assert distintos == []


def test_d3_las_ventanas_de_hoyos_son_una_por_proceso():
    """Given las dos ventanas en memoria, When se piden por el paquete y por su submódulo, Then son la misma."""
    campos = importlib.import_module("src.config.dependencies.campos")
    assert dependencies.get_recent_hole_sample_senders() is campos.get_recent_hole_sample_senders()
    assert dependencies.get_recent_hole_report_senders() is campos.get_recent_hole_report_senders()
    assert dependencies.get_recent_hole_sample_senders() is not (
        dependencies.get_recent_hole_report_senders()
    )


def test_d3_el_lanzador_de_actualizaciones_es_uno_por_proceso(monkeypatch):
    """Given el refresco encendido, When se pide el lanzador dos veces, Then es el mismo y vive en su submódulo."""
    juego = importlib.import_module("src.config.dependencies.comun")
    monkeypatch.setattr(juego, "refresco_activado", lambda _entorno: True)
    monkeypatch.setattr(juego, "LanzadorEnSegundoPlano", lambda *_: MagicMock())
    monkeypatch.setattr(juego, "RFEGHandicapService", lambda **_: None)
    monkeypatch.setattr(juego, "EmailService", lambda: None)
    monkeypatch.setattr(juego, "_lanzador", None)

    primero = dependencies.get_lanzador_de_actualizaciones()

    assert primero is not None
    assert dependencies.get_lanzador_de_actualizaciones() is primero
    assert juego._lanzador is primero


@pytest.mark.parametrize("modulo", SUBMODULOS)
def test_d5_ningun_submodulo_pasa_del_tope(modulo):
    """Given un submódulo, When se cuentan sus líneas, Then no pasa del tope."""
    lineas = len((PAQUETE / f"{modulo}.py").read_text().splitlines())
    assert lineas <= TOPE_DE_LINEAS, f"{modulo}.py tiene {lineas} líneas"


def test_d6_el_parche_del_correo_de_las_pruebas_llega_a_los_tres_servicios():
    """Given el parche que usa conftest, When se piden los servicios de correo, Then son el mock."""
    from unittest.mock import patch

    from tests.conftest import RUTA_DEL_SERVICIO_DE_CORREO

    falso = MagicMock()
    with patch(RUTA_DEL_SERVICIO_DE_CORREO, return_value=falso):
        assert dependencies.get_email_service() is falso
        assert dependencies.get_social_email_service() is falso
        assert dependencies.get_invitation_email_service() is falso
